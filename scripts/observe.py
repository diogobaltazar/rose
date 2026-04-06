#!/usr/bin/env python3
"""
rose observe — session inspector

Usage:
  python scripts/observe.py --list     # list all sessions
  python scripts/observe.py --watch    # live view, updates on file changes
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECTS_DIR    = Path.home() / ".claude" / "projects"
SESSIONS_DIR    = Path.home() / ".claude" / "sessions"
TEAMS_DIR       = Path.home() / ".claude" / "teams"
SUBAGENT_LOG    = Path.home() / ".claude" / "logs" / "subagent-events.jsonl"
MESSAGE_LOG     = Path.home() / ".claude" / "logs" / "message-events.jsonl"

DEBOUNCE_S      = 0.15  # seconds after last event before redrawing
HIGHLIGHT_TTL   = 2.0   # seconds a changed-value highlight stays lit

# ── Rich styles (Matrix palette) ──────────────────────────────────────────────
#
#  colour_number corresponds to xterm-256 palette entries, same as the
#  ANSI escape codes we had before — just expressed as rich style strings.
#
STYLE_NEON     = "bold color(118)"   # session ID / live dot — bright neon green
STYLE_NEON_DIM = "color(28)"         # branch / worktree     — deep matrix green
STYLE_PEARL    = "color(253)"        # title                 — pearl white
STYLE_SILVER   = "color(245)"        # resumed ←             — silver
STYLE_DIM      = "dim"               # dates, sizes, project parent
STYLE_BOLD     = "bold"              # project name
STYLE_DELTA    = "color(39)"         # value-increased highlight — electric blue


# ── Value-change highlight state ──────────────────────────────────────────────
#
#  Tracks previous metric values and highlight expiry times across renders.
#  Keys are "{agent_id}:{metric}" strings.
#
_prev_metrics:      dict[str, float] = {}
_highlight_until:   dict[str, float] = {}


def _check_delta(key: str, value: float) -> bool:
    """Return True if value increased since last call; update state."""
    now  = time.time()
    prev = _prev_metrics.get(key)
    _prev_metrics[key] = value
    if prev is not None and value > prev:
        _highlight_until[key] = now + HIGHLIGHT_TTL
    return now < _highlight_until.get(key, 0)


def _fmt_delta(text: str, key: str, value: float) -> tuple[str, str, str | None, str | None]:
    """Return (text, style, arrow, arrow_style) for a metric field.

    If the value just increased or is still highlighted, returns amber style + ↑ arrow.
    Otherwise returns the normal dim style with no arrow.
    """
    if _check_delta(key, value):
        return text, STYLE_DELTA, " ↑", STYLE_DELTA
    return text, STYLE_DIM, None, None


# ── Git helpers ───────────────────────────────────────────────────────────────

def git(cwd: str, *args) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def git_info(cwd: str) -> dict:
    """Return project root and worktree path for a given cwd."""
    if not cwd or not Path(cwd).exists():
        return {"project": None, "worktree": None}

    git_dir = git(cwd, "rev-parse", "--git-dir")
    if not git_dir:
        return {"project": None, "worktree": None}

    is_worktree = "/.git/worktrees/" in git_dir or git_dir.endswith("/worktrees")

    if is_worktree:
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
        if common_dir:
            project = str(Path(common_dir).resolve().parent)
        else:
            project = None
        worktree = git(cwd, "rev-parse", "--show-toplevel")
    else:
        project  = git(cwd, "rev-parse", "--show-toplevel")
        worktree = None

    return {"project": project, "worktree": worktree}


# ── Native session storage ────────────────────────────────────────────────────

def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def encode_cwd(cwd: str) -> str:
    return cwd.replace("/", "-")


def live_transcripts() -> dict[str, dict]:
    """Return {transcript_stem: {pid, sessionId}} for all live processes."""
    result = {}
    if not SESSIONS_DIR.exists():
        return result
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data       = json.loads(f.read_text())
            pid        = data.get("pid")
            sid        = data.get("sessionId")
            cwd        = data.get("cwd", "")
            started_ms = data.get("startedAt", 0)
        except (json.JSONDecodeError, OSError):
            continue

        if not pid or not cwd:
            continue
        if not pid_running(pid):
            continue

        started_s   = started_ms / 1000
        project_dir = PROJECTS_DIR / encode_cwd(cwd)
        if not project_dir.exists():
            continue

        for transcript in project_dir.glob("*.jsonl"):
            if transcript.stat().st_mtime >= started_s:
                result[transcript.stem] = {"pid": pid, "sessionId": sid}
                break

    return result


# ── Team config ───────────────────────────────────────────────────────────────

def read_team_lead(session_id: str) -> str | None:
    """Return the lead agent_type if session_id is currently leading a team."""
    if not TEAMS_DIR.exists():
        return None
    for team_dir in TEAMS_DIR.iterdir():
        config = team_dir / "config.json"
        if not config.exists():
            continue
        try:
            data = json.loads(config.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("leadSessionId") != session_id:
            continue
        lead_id = data.get("leadAgentId")
        for member in data.get("members", []):
            if member.get("agentId") == lead_id:
                return member.get("agentType")
    return None


# ── Subagent hook log ────────────────────────────────────────────────────────

def read_subagent_hook_states() -> dict[str, str]:
    """Return {agent_id: "live"|"done"} from SubagentStart/SubagentStop hook log.

    The last event for each agent_id is authoritative:
      SubagentStart → "live",  SubagentStop → "done"
    """
    states: dict[str, str] = {}
    if not SUBAGENT_LOG.exists():
        return states
    try:
        with SUBAGENT_LOG.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hook     = entry.get("hook", "")
                payload  = entry.get("payload", {})
                agent_id = payload.get("agent_id")
                if not agent_id:
                    continue
                if hook == "SubagentStart":
                    states[agent_id] = "live"
                elif hook == "SubagentStop":
                    states[agent_id] = "done"
    except OSError:
        pass
    return states


# ── Message hook log ─────────────────────────────────────────────────────────

def read_shutdown_requests() -> dict[str, list[str]]:
    """Return {agent_name: [timestamps]} of shutdown_requests sent via SendMessage.

    When a shutdown_request is sent to an agent by name (e.g. "rose-backlog"),
    SubagentStop may not fire (shutdown via messaging protocol, not natural exit).
    This log lets us correlate agent_type → shutdown timestamp as a done signal.
    """
    shutdowns: dict[str, list[str]] = {}
    if not MESSAGE_LOG.exists():
        return shutdowns
    try:
        with MESSAGE_LOG.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                payload = entry.get("payload", {})
                msg = payload.get("tool_input", {}).get("message", {})
                if not isinstance(msg, dict) or msg.get("type") != "shutdown_request":
                    continue
                to = payload.get("tool_input", {}).get("to", "")
                if to:
                    shutdowns.setdefault(to, []).append(entry.get("ts", ""))
    except OSError:
        pass
    return shutdowns


# ── Transcript reading ────────────────────────────────────────────────────────

def strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
    cleaned = re.sub(r"<[^>]+/>", "", cleaned)
    return cleaned.strip()


def read_transcript(path: Path) -> dict:
    title      = None
    branch     = None
    cwd        = None
    started_at = None
    ended_at   = None
    # agent completion tracking: {agentId: tool_use_id}
    agent_tool_use: dict[str, str] = {}
    # set of tool_use_ids that have a tool_result (agent finished)
    completed_tool_uses: set[str] = set()

    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if started_at is None:
                        started_at = ts
                    ended_at = ts

                etype = entry.get("type")

                if etype == "user" and entry.get("message", {}).get("role") == "user":
                    if cwd is None:
                        cwd = entry.get("cwd")
                    if branch is None:
                        branch = entry.get("gitBranch")
                    if title is None:
                        content = entry.get("message", {}).get("content", "")
                        if isinstance(content, str):
                            cleaned = strip_tags(content)
                            if cleaned:
                                title = cleaned
                    # detect tool_result completions
                    content = entry.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                completed_tool_uses.add(block.get("tool_use_id", ""))

                # link agentId → parentToolUseID via progress entries
                elif etype == "progress":
                    data = entry.get("data", {})
                    if data.get("type") == "agent_progress":
                        agent_id    = data.get("agentId")
                        parent_tuid = entry.get("parentToolUseID")
                        if agent_id and parent_tuid:
                            agent_tool_use[agent_id] = parent_tuid

    except OSError:
        pass

    return {
        "cwd":               cwd,
        "branch":            branch,
        "started_at":        started_at,
        "ended_at":          ended_at,
        "title":             title,
        "size_kb":           round(path.stat().st_size / 1024, 1),
        "agent_tool_use":    agent_tool_use,
        "completed_tool_uses": completed_tool_uses,
    }


def read_subagents(session_dir: Path, agent_tool_use: dict, completed_tool_uses: set, session_live: bool, hook_states: dict[str, str] | None = None, shutdown_requests: dict[str, list[str]] | None = None) -> list[dict]:
    """Read subagent metadata and transcripts from {session_dir}/subagents/."""
    subagents_dir = session_dir / "subagents"
    if not subagents_dir.exists():
        return []

    agents = []
    for meta_file in subagents_dir.glob("agent-*.meta.json"):
        agent_id = meta_file.stem.removeprefix("agent-").removesuffix(".meta")
        # .meta.json stem is "agent-{id}.meta" after glob strips .json
        # actual stem: "agent-a69d496525515eb5e.meta"
        agent_id = meta_file.name.removeprefix("agent-").removesuffix(".meta.json")

        try:
            meta = json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        agent_type  = meta.get("agentType", "unknown")
        description = meta.get("description", "")

        jsonl_file  = subagents_dir / f"agent-{agent_id}.jsonl"
        started_at  = None
        tool_use_count = 0
        size_kb     = None

        agent_cwd   = None
        jsonl_mtime = None
        if jsonl_file.exists():
            st      = jsonl_file.stat()
            size_kb = round(st.st_size / 1024, 1)
            jsonl_mtime = st.st_mtime
            try:
                with jsonl_file.open() as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if started_at is None:
                            started_at = entry.get("timestamp")
                        if agent_cwd is None and entry.get("type") == "user":
                            agent_cwd = entry.get("cwd")
                        if entry.get("type") == "assistant":
                            content = entry.get("message", {}).get("content", [])
                            if isinstance(content, list):
                                tool_use_count += sum(
                                    1 for b in content
                                    if isinstance(b, dict) and b.get("type") == "tool_use"
                                )
            except OSError:
                pass

        agent_branch  = git(agent_cwd, "rev-parse", "--abbrev-ref", "HEAD") if agent_cwd else None
        agent_gi      = git_info(agent_cwd) if agent_cwd else {"project": None, "worktree": None}

        # Determine live/done — in order of reliability:
        #  1. SubagentStop fired → definitively done
        #  2. tool_result in parent transcript → done (SubagentStop may have been missed)
        #  3. SubagentStart fired, no Stop, no tool_result → live
        #  4. No hook data, no transcript link → conservative "done"
        tool_use_id = agent_tool_use.get(agent_id, "")
        tool_result_done = bool(tool_use_id and tool_use_id in completed_tool_uses)

        stale = jsonl_mtime is not None and (time.time() - jsonl_mtime) > 120

        # shutdown_request sent to this agent_type after it started → done
        shutdown_sent = False
        if shutdown_requests and started_at:
            for ts in shutdown_requests.get(agent_type, []):
                if ts >= started_at:
                    shutdown_sent = True
                    break

        if hook_states and agent_id in hook_states:
            if hook_states[agent_id] == "done":
                is_done = True                   # SubagentStop fired
            elif tool_result_done:
                is_done = True                   # SubagentStop missed; tool_result is ground truth
            elif shutdown_sent:
                is_done = True                   # shutdown_request sent; SubagentStop won't fire
            elif stale:
                is_done = True                   # orphaned Start + silent file — agent is gone
            else:
                is_done = False                  # genuinely live
        else:
            if tool_use_id:
                is_done = tool_result_done       # fall back to transcript join
            else:
                is_done = True                   # no signal — conservative default
        status = "live" if (not is_done) and session_live else "done"

        agents.append({
            "agent_id":      agent_id,
            "agent_type":    agent_type,
            "description":   description,
            "started_at":    started_at,
            "size_kb":       size_kb,
            "tool_use_count": tool_use_count,
            "status":        status,
            "cwd":           agent_cwd,
            "branch":        agent_branch,
            "worktree":      agent_gi.get("worktree"),
        })

    agents.sort(key=lambda a: a["started_at"] or "")
    return agents


# ── Session scanning ──────────────────────────────────────────────────────────

def scan_sessions() -> list[dict]:
    live              = live_transcripts()
    hook_states       = read_subagent_hook_states()
    shutdown_requests = read_shutdown_requests()
    sessions          = []
    matched_pids      = set()

    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            for transcript in project_dir.glob("*.jsonl"):
                session_id = transcript.stem
                info       = read_transcript(transcript)
                gi         = git_info(info["cwd"] or "")

                if session_id in live:
                    status      = "live"
                    pid         = live[session_id]["pid"]
                    process_sid = live[session_id]["sessionId"]
                    matched_pids.add(pid)
                else:
                    status      = "done"
                    pid         = None
                    process_sid = None

                session_dir = transcript.parent / session_id
                agents      = read_subagents(
                    session_dir,
                    info["agent_tool_use"],
                    info["completed_tool_uses"],
                    status == "live",
                    hook_states,
                    shutdown_requests,
                )
                team_lead = read_team_lead(session_id) if status == "live" else None
                sessions.append({
                    "session_id":  session_id,
                    "process_sid": process_sid,
                    "pid":         pid,
                    "status":      status,
                    "project":     gi["project"],
                    "worktree":    gi["worktree"],
                    "branch":      info["branch"],
                    "started_at":  info["started_at"],
                    "title":       info["title"],
                    "size_kb":     info["size_kb"],
                    "agents":      agents,
                    "team_lead":   team_lead,
                })

    # Live processes with no transcript yet
    if SESSIONS_DIR.exists():
        for f in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                pid  = data.get("pid")
                sid  = data.get("sessionId")
                cwd  = data.get("cwd", "")
                ms   = data.get("startedAt", 0)
            except (json.JSONDecodeError, OSError):
                continue
            if not pid or not pid_running(pid) or pid in matched_pids:
                continue
            gi = git_info(cwd)
            sessions.append({
                "session_id":  sid,
                "process_sid": None,
                "pid":         pid,
                "status":      "live",
                "project":     gi["project"] or cwd,
                "worktree":    gi["worktree"],
                "branch":      git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
                "started_at":  datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(),
                "title":       None,
                "size_kb":     None,
                "agents":      [],
            })

    sessions.sort(key=lambda s: s["started_at"] or "", reverse=True)
    return sessions


# ── Rendering ─────────────────────────────────────────────────────────────────

def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%d-%b-%Y %H:%M:%S").upper()
    except Exception:
        return iso[:19]


def fmt_size(size_kb: float | None) -> str:
    if size_kb is None:
        return "0 KB"
    if size_kb >= 1024:
        return f"{size_kb / 1024:.1f} MB"
    return f"{size_kb} KB"


def render_sessions() -> "Text":
    from rich.text import Text

    sessions = scan_sessions()
    out = Text()

    if not sessions:
        out.append("\n  no sessions found\n")
        return out

    sep = "  " + "─" * 72

    for s in sessions:
        status     = s["status"]
        session_id = s["session_id"]
        process_sid= s.get("process_sid") or ""
        pid        = s["pid"]
        branch     = s["branch"]
        worktree   = s["worktree"]
        title      = s["title"] or ""
        project    = s["project"] or ""
        started    = fmt_dt(s["started_at"])
        size       = fmt_size(s["size_kb"])

        # separator
        out.append("\n" + sep + "\n", style=STYLE_DIM)

        # dot
        out.append("  ")
        if status == "live":
            out.append("●", style=STYLE_NEON + " blink")
        else:
            out.append("○", style=STYLE_DIM)

        # session id
        out.append("  ")
        out.append(session_id, style=STYLE_NEON)

        # resumed indicator
        if process_sid and process_sid != session_id:
            out.append("  ")
            out.append("←", style=STYLE_SILVER)
            out.append(process_sid, style=STYLE_DIM)

        # pid
        if pid:
            out.append("  ")
            out.append(f"pid {pid}", style=STYLE_DIM)

        out.append("\n")

        # title
        if title:
            out.append("  ")
            out.append(title, style=STYLE_PEARL)
            out.append("\n")

        # meta row
        meta_parts: list[tuple[str, str]] = []

        if project:
            p = Path(project)
            meta_parts.append((str(p.parent) + "/", STYLE_DIM))
            meta_parts.append((p.name, STYLE_BOLD))

        if branch:
            meta_parts.append((f"⎇ {branch}", STYLE_NEON_DIM))

        if worktree:
            meta_parts.append((f"worktree {Path(worktree).name}", STYLE_NEON_DIM))

        meta_parts.append((started, STYLE_DIM))

        out.append("  ")
        dot_sep = ("  ·  ", STYLE_DIM)
        for i, (text, style) in enumerate(meta_parts):
            if i > 0:
                out.append(*dot_sep)
            out.append(text, style=style)

        # session KB — with delta highlight
        out.append(*dot_sep)
        if s["size_kb"] is not None:
            t, st, arrow, as_ = _fmt_delta(size, session_id + ":kb", s["size_kb"])
            out.append(t, style=st)
            if arrow:
                out.append(arrow, style=as_)
        else:
            out.append(size, style=STYLE_DIM)

        out.append("\n")

        # agents — group by agent_type, one row per type
        agents    = s.get("agents", [])
        team_lead = s.get("team_lead")
        if agents or team_lead:
            # group: {agent_type: [invocations...]}  (sorted by started_at already)
            groups: dict[str, list] = {}
            for a in agents:
                groups.setdefault(a["agent_type"], []).append(a)

            # build one summary row per agent type
            rows = []
            for agent_type, invocations in groups.items():
                last        = invocations[-1]
                row_status  = "live" if any(a["status"] == "live" for a in invocations) else "done"
                count       = len(invocations)
                total_kb    = round(sum((a["size_kb"] or 0) for a in invocations), 1)
                total_calls = sum(a["tool_use_count"] for a in invocations)
                rows.append({
                    "agent_type":  agent_type,
                    "agent_id":    last["agent_id"],
                    "description": last["description"],
                    "status":      row_status,
                    "count":       count,
                    "total_kb":    total_kb,
                    "total_calls": total_calls,
                    "is_lead":     False,
                    "cwd":         last.get("cwd"),
                    "branch":      last.get("branch"),
                    "worktree":    last.get("worktree"),
                })

            if team_lead:
                rows.insert(0, {
                    "agent_type":  team_lead,
                    "agent_id":    "",
                    "description": "team-lead",
                    "status":      status,
                    "count":       None,
                    "total_kb":    None,
                    "total_calls": None,
                    "is_lead":     True,
                })

            col_type  = max(len(r["agent_type"])                              for r in rows)
            col_count = max(len(f"×{r['count']}") if r["count"] else 0        for r in rows)
            col_size  = max(len(fmt_size(r["total_kb"])) if r["total_kb"] else 0 for r in rows)
            col_calls = max(len(str(r["total_calls"])) if r["total_calls"] is not None else 0 for r in rows)
            dot_sep   = ("  ·  ", STYLE_DIM)

            for r in rows:
                atype  = r["agent_type"].ljust(col_type)
                adesc  = r["description"] or ""

                out.append("     ")
                if r["status"] == "live":
                    out.append("●", style=STYLE_NEON + " blink")
                else:
                    out.append("○", style=STYLE_DIM)
                out.append("  ")
                out.append(atype, style=STYLE_NEON_DIM)

                if r["is_lead"]:
                    # lead row — name · team-lead only
                    out.append(*dot_sep)
                    out.append("team-lead", style=STYLE_DIM)
                else:
                    # subagent row — name · id · ×N · KB · ⚙ calls
                    aid    = r["agent_id"][:8]
                    acount = f"×{r['count']}".rjust(col_count)
                    asize  = fmt_size(r["total_kb"]).rjust(col_size)
                    acalls = str(r["total_calls"]).rjust(col_calls)
                    pfx    = session_id + ":" + r["agent_type"] + ":"  # scoped per session

                    out.append(*dot_sep)
                    out.append(aid, style=STYLE_DIM)

                    out.append(*dot_sep)
                    t, s, arrow, as_ = _fmt_delta(acount, pfx + "count", r["count"])
                    out.append(t, style=s)
                    if arrow:
                        out.append(arrow, style=as_)

                    out.append(*dot_sep)
                    t, s, arrow, as_ = _fmt_delta(asize, pfx + "kb", r["total_kb"])
                    out.append(t, style=s)
                    if arrow:
                        out.append(arrow, style=as_)

                    out.append(*dot_sep)
                    t, s, arrow, as_ = _fmt_delta(f"⚙ {acalls}", pfx + "calls", r["total_calls"])
                    out.append(t, style=s)
                    if arrow:
                        out.append(arrow, style=as_)

                out.append("\n")

                # line 2 — description (subagents only)
                if adesc and not r["is_lead"]:
                    out.append("          ")
                    out.append(adesc, style=STYLE_DIM)
                    out.append("\n")

                # line 3 — location info (cwd/branch/worktree) when relevant
                if not r["is_lead"] and r.get("cwd") and (r.get("worktree") is not None or r.get("branch") != s["branch"]):
                    home = Path.home()
                    rcwd = Path(r["cwd"])
                    try:
                        display_cwd = "~/" + str(rcwd.relative_to(home))
                    except ValueError:
                        display_cwd = str(rcwd)
                    out.append("          ")
                    out.append(display_cwd, style=STYLE_DIM)
                    if r.get("branch"):
                        out.append(f"  ⎇ {r['branch']}", style=STYLE_NEON_DIM)
                    if r.get("worktree") is not None:
                        out.append("  [worktree]", style=STYLE_NEON_DIM)
                    out.append("\n")

    out.append(sep + "\n", style=STYLE_DIM)
    return out


# ── List (one-shot) ───────────────────────────────────────────────────────────

def list_sessions():
    from rich.console import Console
    Console().print(render_sessions())


# ── Watch mode ────────────────────────────────────────────────────────────────

def watch_sessions():
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("watchdog is required for --watch:  pip install watchdog")
        sys.exit(1)

    from rich.console import Console
    from rich.live import Live

    console = Console()
    live    = Live(render_sessions(), console=console, auto_refresh=False)

    timer: threading.Timer | None = None
    lock = threading.Lock()

    def refresh():
        live.update(render_sessions(), refresh=True)
        # schedule another refresh when the earliest active highlight expires
        now     = time.time()
        pending = [exp - now for exp in _highlight_until.values() if exp > now]
        if pending:
            t = threading.Timer(min(pending) + 0.05, schedule_refresh)
            t.daemon = True
            t.start()

    def schedule_refresh():
        with lock:
            nonlocal timer
            if timer is not None:
                timer.cancel()
            timer = threading.Timer(0, refresh)
            timer.daemon = True
            timer.start()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            nonlocal timer
            if event.is_directory:
                return
            with lock:
                if timer is not None:
                    timer.cancel()
                timer = threading.Timer(DEBOUNCE_S, refresh)
                timer.daemon = True
                timer.start()

    observer = Observer()
    handler  = Handler()

    logs_dir = SUBAGENT_LOG.parent  # same dir as MESSAGE_LOG
    for watch_dir in (SESSIONS_DIR, PROJECTS_DIR, TEAMS_DIR, logs_dir):
        watch_dir.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(watch_dir), recursive=True)

    observer.start()

    try:
        with live:
            observer.join()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if args and args[0] == "--list":
        list_sessions()
    elif args and args[0] == "--watch":
        watch_sessions()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
