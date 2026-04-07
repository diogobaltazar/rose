"""
rose observe — session inspector

Commands:
  rose observe watch    # live tabbed view, updates on file changes
"""

import json
import os
import re
import select
import subprocess
import sys
import termios
import threading
import time
import tty
from datetime import datetime, timezone
from pathlib import Path

import typer

PROJECTS_DIR    = Path.home() / ".claude" / "projects"
SESSIONS_DIR    = Path.home() / ".claude" / "sessions"
TEAMS_DIR       = Path.home() / ".claude" / "teams"
SUBAGENT_LOG    = Path.home() / ".claude" / "logs" / "subagent-events.jsonl"
MESSAGE_LOG     = Path.home() / ".claude" / "logs" / "message-events.jsonl"
OBSERVE_CONFIG  = Path.home() / ".claude" / "observe-config.json"

DEBOUNCE_S      = 0.15   # seconds after last event before redrawing
HIGHLIGHT_TTL   = 2.0    # seconds a changed-value highlight stays lit

# ── Rich styles ────────────────────────────────────────────────────────────────
STYLE_NEON     = "bold color(118)"   # live dot / session ID
STYLE_NEON_DIM = "color(28)"         # branch / worktree / agent name
STYLE_PEARL    = "color(253)"        # feature one-liner
STYLE_SILVER   = "color(245)"        # ← resume arrow
STYLE_DIM      = "dim"               # labels, dates, secondary info
STYLE_BOLD     = "bold"              # project name
STYLE_KEY      = "color(245)"        # header key column
STYLE_VAL      = "color(253)"        # header value column
STYLE_DELTA    = "color(39)"         # value-increased highlight
STYLE_TAB_SEL  = "bold reverse"      # selected tab
STYLE_TAB      = "color(245)"        # unselected tab

# ── Value-change highlight state ──────────────────────────────────────────────
_prev_metrics:    dict[str, float] = {}
_highlight_until: dict[str, float] = {}


def _check_delta(key: str, value: float) -> bool:
    now  = time.time()
    prev = _prev_metrics.get(key)
    _prev_metrics[key] = value
    if prev is not None and value > prev:
        _highlight_until[key] = now + HIGHLIGHT_TTL
    return now < _highlight_until.get(key, 0)


def _fmt_delta(text: str, key: str, value: float) -> tuple[str, str, str | None, str | None]:
    if _check_delta(key, value):
        return text, STYLE_DELTA, " ↑", STYLE_DELTA
    return text, STYLE_DIM, None, None


# ── Config / pricing ──────────────────────────────────────────────────────────

_pricing_cache: tuple | None = None


def _load_pricing() -> tuple[dict, dict]:
    global _pricing_cache
    if _pricing_cache is not None:
        return _pricing_cache
    try:
        cfg = json.loads(OBSERVE_CONFIG.read_text())
    except (OSError, json.JSONDecodeError):
        cfg = {}
    mp = cfg.get("model_pricing", {})
    fp = cfg.get("fallback_pricing", {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30})
    _pricing_cache = (mp, fp)
    return _pricing_cache


def _usd_for_usage(usage: dict, model: str | None) -> float:
    mp, fp = _load_pricing()
    rates  = mp.get(model or "", fp)
    inp    = usage.get("input_tokens", 0)
    out    = usage.get("output_tokens", 0)
    cw     = usage.get("cache_creation_input_tokens", 0)
    cr     = usage.get("cache_read_input_tokens", 0)
    return (
        inp * rates["input"]       / 1_000_000 +
        out * rates["output"]      / 1_000_000 +
        cw  * rates["cache_write"] / 1_000_000 +
        cr  * rates["cache_read"]  / 1_000_000
    )


# ── Git helpers ────────────────────────────────────────────────────────────────

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
    if not cwd or not Path(cwd).exists():
        return {"project": None, "worktree": None}
    git_dir = git(cwd, "rev-parse", "--git-dir")
    if not git_dir:
        return {"project": None, "worktree": None}
    is_worktree = "/.git/worktrees/" in git_dir or git_dir.endswith("/worktrees")
    if is_worktree:
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
        project    = str(Path(common_dir).resolve().parent) if common_dir else None
        worktree   = git(cwd, "rev-parse", "--show-toplevel")
    else:
        project  = git(cwd, "rev-parse", "--show-toplevel")
        worktree = None
    return {"project": project, "worktree": worktree}


# ── Formatting helpers ─────────────────────────────────────────────────────────

def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%d-%b-%Y %H:%M:%S").upper()
    except Exception:
        return iso[:19]


def fmt_size(kb: float | None) -> str:
    if kb is None:
        return "—"
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb:.1f} KB"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def fmt_tokens(n: int | None) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_usd(usd: float | None) -> str:
    if usd is None:
        return "—"
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.3f}"


def strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
    cleaned = re.sub(r"<[^>]+/>", "", cleaned)
    return cleaned.strip()


# ── Native session storage ─────────────────────────────────────────────────────

def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def encode_cwd(cwd: str) -> str:
    return cwd.replace("/", "-")


def live_transcripts() -> dict[str, dict]:
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
        if not pid or not cwd or not pid_running(pid):
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


# ── Team config ────────────────────────────────────────────────────────────────

def read_team_config(session_id: str) -> dict | None:
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
        if data.get("leadSessionId") == session_id:
            return data
    return None


def team_member_agent_ids(team_config: dict) -> set[str]:
    lead_id = team_config.get("leadAgentId", "")
    return {
        m["agentId"]
        for m in team_config.get("members", [])
        if m.get("agentId") != lead_id
    }


def team_lead_type(team_config: dict) -> str | None:
    lead_id = team_config.get("leadAgentId", "")
    for m in team_config.get("members", []):
        if m.get("agentId") == lead_id:
            return m.get("agentType")
    return None


# ── Hook logs ──────────────────────────────────────────────────────────────────

def read_subagent_hook_states() -> dict[str, str]:
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


def read_shutdown_requests() -> dict[str, list[str]]:
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


# ── Transcript reading ─────────────────────────────────────────────────────────

def _accumulate_usage(entry: dict, totals: dict) -> None:
    msg   = entry.get("message", {})
    usage = msg.get("usage")
    if not usage:
        return
    model = msg.get("model") or entry.get("model")
    if model == "<synthetic>":
        model = None
    totals["input"]       += usage.get("input_tokens", 0)
    totals["output"]      += usage.get("output_tokens", 0)
    totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
    totals["cache_read"]  += usage.get("cache_read_input_tokens", 0)
    totals["usd"]         += _usd_for_usage(usage, model)


def _empty_usage() -> dict:
    return {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "usd": 0.0}


def read_transcript(path: Path) -> dict:
    title        = None
    branch       = None
    cwd          = None
    started_at   = None
    ended_at     = None
    tool_count   = 0
    usage        = _empty_usage()
    agent_tool_use:      dict[str, str] = {}
    completed_tool_uses: set[str]       = set()

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

                if etype == "user":
                    msg = entry.get("message", {})
                    if msg.get("role") == "user":
                        if cwd is None:
                            cwd = entry.get("cwd")
                        if branch is None:
                            branch = entry.get("gitBranch")
                        if title is None:
                            content = msg.get("content", "")
                            if isinstance(content, str):
                                cleaned = strip_tags(content)
                                if cleaned:
                                    title = cleaned
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    completed_tool_uses.add(block.get("tool_use_id", ""))

                elif etype == "assistant":
                    content = entry.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        tool_count += sum(
                            1 for b in content
                            if isinstance(b, dict) and b.get("type") == "tool_use"
                        )
                    _accumulate_usage(entry, usage)

                elif etype == "progress":
                    data = entry.get("data", {})
                    if data.get("type") == "agent_progress":
                        agent_id    = data.get("agentId")
                        parent_tuid = entry.get("parentToolUseID")
                        if agent_id and parent_tuid:
                            agent_tool_use[agent_id] = parent_tuid

    except OSError:
        pass

    total_tokens = usage["input"] + usage["output"] + usage["cache_write"] + usage["cache_read"]

    return {
        "cwd":                cwd,
        "branch":             branch,
        "started_at":         started_at,
        "ended_at":           ended_at,
        "title":              title,
        "size_kb":            round(path.stat().st_size / 1024, 1),
        "tool_count":         tool_count,
        "tokens":             total_tokens,
        "usd":                usage["usd"],
        "agent_tool_use":     agent_tool_use,
        "completed_tool_uses": completed_tool_uses,
    }


def read_subagents(
    session_dir: Path,
    agent_tool_use: dict,
    completed_tool_uses: set,
    session_live: bool,
    hook_states: dict[str, str] | None = None,
    shutdown_requests: dict[str, list[str]] | None = None,
) -> list[dict]:
    subagents_dir = session_dir / "subagents"
    if not subagents_dir.exists():
        return []

    agents = []
    for meta_file in subagents_dir.glob("agent-*.meta.json"):
        agent_id = meta_file.name.removeprefix("agent-").removesuffix(".meta.json")
        try:
            meta = json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        agent_type  = meta.get("agentType", "unknown")
        description = meta.get("description", "")

        jsonl_file   = subagents_dir / f"agent-{agent_id}.jsonl"
        started_at   = None
        ended_at     = None
        tool_count   = 0
        size_kb      = None
        agent_cwd    = None
        jsonl_mtime  = None
        usage        = _empty_usage()

        if jsonl_file.exists():
            st          = jsonl_file.stat()
            size_kb     = round(st.st_size / 1024, 1)
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
                        ts = entry.get("timestamp")
                        if ts:
                            if started_at is None:
                                started_at = ts
                            ended_at = ts
                        if agent_cwd is None and entry.get("type") == "user":
                            agent_cwd = entry.get("cwd")
                        if entry.get("type") == "assistant":
                            content = entry.get("message", {}).get("content", [])
                            if isinstance(content, list):
                                tool_count += sum(
                                    1 for b in content
                                    if isinstance(b, dict) and b.get("type") == "tool_use"
                                )
                            _accumulate_usage(entry, usage)
            except OSError:
                pass

        agent_branch = git(agent_cwd, "rev-parse", "--abbrev-ref", "HEAD") if agent_cwd else None
        agent_gi     = git_info(agent_cwd) if agent_cwd else {"project": None, "worktree": None}

        tool_use_id      = agent_tool_use.get(agent_id, "")
        tool_result_done = bool(tool_use_id and tool_use_id in completed_tool_uses)
        stale            = jsonl_mtime is not None and (time.time() - jsonl_mtime) > 120

        shutdown_sent = False
        if shutdown_requests and started_at:
            for ts in shutdown_requests.get(agent_type, []):
                if ts >= started_at:
                    shutdown_sent = True
                    break

        if hook_states and agent_id in hook_states:
            is_done = hook_states[agent_id] == "done" or tool_result_done or shutdown_sent or stale
        else:
            is_done = tool_result_done if tool_use_id else True

        status = "live" if (not is_done) and session_live else "done"

        duration = None
        if started_at and ended_at:
            try:
                t0 = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                duration = (t1 - t0).total_seconds()
            except Exception:
                pass

        total_tokens = usage["input"] + usage["output"] + usage["cache_write"] + usage["cache_read"]

        agents.append({
            "agent_id":    agent_id,
            "agent_type":  agent_type,
            "description": description,
            "started_at":  started_at,
            "ended_at":    ended_at,
            "size_kb":     size_kb,
            "tool_count":  tool_count,
            "tokens":      total_tokens,
            "usd":         usage["usd"],
            "duration":    duration,
            "status":      status,
            "cwd":         agent_cwd,
            "branch":      agent_branch,
            "worktree":    agent_gi.get("worktree"),
        })

    agents.sort(key=lambda a: a["started_at"] or "")
    return agents


# ── Meta.json ──────────────────────────────────────────────────────────────────

def read_session_meta(session_dir: Path) -> dict:
    try:
        return json.loads((session_dir / "meta.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


# ── Session scanning ───────────────────────────────────────────────────────────

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

                session_dir  = transcript.parent / session_id
                agents       = read_subagents(
                    session_dir,
                    info["agent_tool_use"],
                    info["completed_tool_uses"],
                    status == "live",
                    hook_states,
                    shutdown_requests,
                )
                team_config  = read_team_config(session_id) if status == "live" else None
                session_meta = read_session_meta(session_dir)

                # Session-wide duration (min start → max end across session + all agents)
                all_starts = [s for s in [info["started_at"]] + [a["started_at"] for a in agents] if s]
                all_ends   = [e for e in [info["ended_at"]]   + [a["ended_at"]   for a in agents] if e]
                duration   = None
                if all_starts and all_ends:
                    try:
                        t0 = datetime.fromisoformat(min(all_starts).replace("Z", "+00:00"))
                        t1 = datetime.fromisoformat(max(all_ends).replace("Z", "+00:00"))
                        duration = (t1 - t0).total_seconds()
                    except Exception:
                        pass

                total_kb     = round((info["size_kb"] or 0) + sum((a["size_kb"] or 0) for a in agents), 1)
                total_tools  = info["tool_count"] + sum(a["tool_count"] for a in agents)
                total_tokens = info["tokens"] + sum(a["tokens"] for a in agents)
                total_usd    = info["usd"] + sum(a["usd"] for a in agents)

                sessions.append({
                    "session_id":   session_id,
                    "process_sid":  process_sid,
                    "pid":          pid,
                    "status":       status,
                    "project":      gi["project"],
                    "worktree":     gi["worktree"],
                    "branch":       info["branch"],
                    "started_at":   info["started_at"],
                    "title":        info["title"],
                    "duration":     duration,
                    "total_kb":     total_kb,
                    "total_tools":  total_tools,
                    "total_tokens": total_tokens,
                    "total_usd":    total_usd,
                    "agents":       agents,
                    "team_config":  team_config,
                    "meta":         session_meta,
                })

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
                "session_id":   sid,
                "process_sid":  None,
                "pid":          pid,
                "status":       "live",
                "project":      gi["project"] or cwd,
                "worktree":     gi["worktree"],
                "branch":       git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
                "started_at":   datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(),
                "title":        None,
                "duration":     None,
                "total_kb":     None,
                "total_tools":  0,
                "total_tokens": 0,
                "total_usd":    0.0,
                "agents":       [],
                "team_config":  None,
                "meta":         {},
            })

    sessions.sort(key=lambda s: s["started_at"] or "", reverse=True)
    return sessions


# ── Rendering ──────────────────────────────────────────────────────────────────

def _header_row(out, label: str, value: str, delta_key: str | None = None, delta_val: float = 0) -> None:
    out.append("  ")
    out.append(f"{label:<10}", style=STYLE_KEY)
    out.append("  ")
    if delta_key and _check_delta(delta_key, delta_val):
        out.append(value, style=STYLE_DELTA)
        out.append(" ↑", style=STYLE_DELTA)
    else:
        out.append(value, style=STYLE_VAL)
    out.append("\n")


def _agent_summary_row(out, agent_rows: list[dict], session_id: str) -> None:
    if not agent_rows:
        return
    total_kb     = round(sum(r["total_kb"]     for r in agent_rows), 1)
    total_tools  = sum(r["total_tools"]  for r in agent_rows)
    total_tokens = sum(r["total_tokens"] for r in agent_rows)
    total_usd    = sum(r["total_usd"]    for r in agent_rows)
    total_dur    = sum(r["duration"]     for r in agent_rows)
    total_inv    = sum(r["invocations"]  for r in agent_rows)

    pfx = session_id + ":agents:"
    parts = [
        (fmt_size(total_kb),          pfx + "kb",    total_kb),
        (f"⚙ {total_tools}",          pfx + "tools", total_tools),
        (fmt_duration(total_dur),      pfx + "dur",   total_dur),
        (fmt_tokens(total_tokens),     pfx + "tok",   total_tokens),
        (fmt_usd(total_usd),           pfx + "usd",   total_usd),
        (f"×{total_inv}",              pfx + "inv",   total_inv),
    ]
    out.append("     ")
    dot = ("  ·  ", STYLE_DIM)
    for i, (txt, key, val) in enumerate(parts):
        if i:
            out.append(*dot)
        t, st, arrow, as_ = _fmt_delta(txt, key, val)
        out.append(t, style=st)
        if arrow:
            out.append(arrow, style=as_)
    out.append("\n\n")


def _render_session_body(s: dict) -> "Text":
    """Render a single session's detail view (header, metrics, agents)."""
    from rich.text import Text

    out = Text()

    status      = s["status"]
    session_id  = s["session_id"]
    process_sid = s.get("process_sid") or ""
    branch      = s["branch"]
    project     = s["project"] or ""
    meta        = s.get("meta", {})
    agents      = s.get("agents", [])
    team_config = s.get("team_config")
    home        = Path.home()

    sep = "  " + "─" * 76

    out.append("\n" + sep + "\n", style=STYLE_DIM)

    # Project name + live dot
    project_name = Path(project).name if project else "—"
    out.append("  ")
    if status == "live":
        out.append("● ", style=STYLE_NEON + " blink")
    else:
        out.append("○ ", style=STYLE_DIM)
    out.append(project_name, style=STYLE_BOLD)
    out.append("\n")

    # Feature one-liner
    title = (s.get("title") or meta.get("feature") or "").strip()
    if title:
        if len(title) > 74:
            title = title[:71] + "…"
        out.append("  ")
        out.append(title, style=STYLE_PEARL)
        out.append("\n")

    out.append("\n")

    # Session ID + chain
    sid_short  = session_id[:8]
    psid_short = process_sid[:8] if (process_sid and process_sid != session_id) else None
    chain = sid_short + ("  ←  " + psid_short if psid_short else "")
    _header_row(out, "session", chain)
    _header_row(out, "created", fmt_dt(s["started_at"]))
    if project:
        _header_row(out, "tree", project)
    if branch:
        _header_row(out, "branch", branch)

    # meta fields (from meta.json)
    issues = meta.get("issues")
    if issues:
        val = "  ".join(issues) if isinstance(issues, list) else str(issues)
    else:
        val = "none"
    _header_row(out, "issue(s)", val)
    _header_row(out, "tag", meta.get("tag") or "none")
    _header_row(out, "PR",  meta.get("pr")  or "none")

    # aggregate metrics
    pfx = session_id + ":"
    _header_row(out, "memory",
        fmt_size(s["total_kb"]),
        pfx + "kb",    s["total_kb"] or 0)
    _header_row(out, "tool",
        str(s["total_tools"]),
        pfx + "tools", s["total_tools"])
    _header_row(out, "time",
        fmt_duration(s["duration"]),
        pfx + "dur",   s["duration"] or 0)
    _header_row(out, "token",
        fmt_tokens(s["total_tokens"]),
        pfx + "tok",   s["total_tokens"])
    _header_row(out, "USD",
        fmt_usd(s["total_usd"]),
        pfx + "usd",   s["total_usd"])

    if not agents:
        out.append("\n")
        out.append(sep + "\n", style=STYLE_DIM)
        return out

    out.append("\n")

    # Build per-type agent rows
    team_member_ids = team_member_agent_ids(team_config) if team_config else set()
    lead_type       = team_lead_type(team_config) if team_config else None

    groups: dict[str, list] = {}
    for a in agents:
        groups.setdefault(a["agent_type"], []).append(a)

    agent_rows: list[dict] = []
    for agent_type, invocations in groups.items():
        last      = invocations[-1]
        row_live  = any(a["status"] == "live" for a in invocations)
        in_team   = any(a["agent_id"] in team_member_ids for a in invocations)
        agent_rows.append({
            "agent_type":   agent_type,
            "agent_id":     last["agent_id"],
            "status":       "live" if row_live else "done",
            "invocations":  len(invocations),
            "total_kb":     round(sum((a["size_kb"] or 0) for a in invocations), 1),
            "total_tools":  sum(a["tool_count"] for a in invocations),
            "total_tokens": sum(a["tokens"] for a in invocations),
            "total_usd":    sum(a["usd"] for a in invocations),
            "duration":     sum((a["duration"] or 0) for a in invocations),
            "in_team":      in_team,
            "cwd":          last.get("cwd"),
            "branch":       last.get("branch"),
            "worktree":     last.get("worktree"),
        })

    _agent_summary_row(out, agent_rows, session_id)

    # Column widths
    col_type = max(len(r["agent_type"])                for r in agent_rows)
    col_size = max(len(fmt_size(r["total_kb"]))        for r in agent_rows)
    col_tool = max(len(f"⚙ {r['total_tools']}")       for r in agent_rows)
    col_dur  = max(len(fmt_duration(r["duration"]))    for r in agent_rows)
    col_tok  = max(len(fmt_tokens(r["total_tokens"]))  for r in agent_rows)
    col_usd  = max(len(fmt_usd(r["total_usd"]))        for r in agent_rows)
    col_inv  = max(len(f"×{r['invocations']}")         for r in agent_rows)

    dot = ("  ·  ", STYLE_DIM)

    def _render_row(r: dict, line_pfx: str, body_pfx: str) -> None:
        atype = r["agent_type"].ljust(col_type)
        aid   = r["agent_id"][:8]
        k     = session_id + ":" + r["agent_type"] + ":"

        out.append(line_pfx)
        if r["status"] == "live":
            out.append("○ ", style=STYLE_NEON + " blink")
        else:
            out.append("○ ", style=STYLE_DIM)
        out.append(atype, style=STYLE_NEON_DIM)

        for txt, key, val in [
            (fmt_size(r["total_kb"]).rjust(col_size),         k+"kb",    r["total_kb"]),
            (f"⚙ {r['total_tools']}".rjust(col_tool),         k+"tools", r["total_tools"]),
            (fmt_duration(r["duration"]).rjust(col_dur),       k+"dur",   r["duration"]),
            (fmt_tokens(r["total_tokens"]).rjust(col_tok),     k+"tok",   r["total_tokens"]),
            (fmt_usd(r["total_usd"]).rjust(col_usd),           k+"usd",   r["total_usd"]),
            (f"×{r['invocations']}".rjust(col_inv),            k+"inv",   r["invocations"]),
        ]:
            out.append(*dot)
            t, st, arrow, as_ = _fmt_delta(txt, key, val)
            out.append(t, style=st)
            if arrow:
                out.append(arrow, style=as_)
        out.append("\n")

        # agent ID
        out.append(body_pfx + aid + "\n", style=STYLE_DIM)

        # cwd / branch / worktree (only if different from session)
        if r.get("cwd") and (r.get("worktree") is not None or r.get("branch") != branch):
            rcwd = Path(r["cwd"])
            try:
                display_cwd = "~/" + str(rcwd.relative_to(home))
            except ValueError:
                display_cwd = str(rcwd)
            out.append(body_pfx, style=STYLE_DIM)
            out.append(display_cwd, style=STYLE_DIM)
            if r.get("branch"):
                out.append(f"  ⎇ {r['branch']}", style=STYLE_NEON_DIM)
            if r.get("worktree") is not None:
                out.append(f"  worktree {Path(r['worktree']).name}", style=STYLE_NEON_DIM)
            out.append("\n")

    standalone = [r for r in agent_rows if not r["in_team"]]
    team_rows  = [r for r in agent_rows if r["in_team"]]

    # Standalone agents (flat)
    for r in standalone:
        _render_row(r, line_pfx="     ", body_pfx="        ")

    # Team lead + tree children
    if lead_type or team_rows:
        out.append("     ")
        if status == "live":
            out.append("○ ", style=STYLE_NEON + " blink")
        else:
            out.append("○ ", style=STYLE_DIM)
        out.append((lead_type or "rose").ljust(col_type), style=STYLE_NEON_DIM)
        out.append(*dot)
        out.append("team-lead", style=STYLE_DIM)
        out.append("\n")

        if team_rows:
            out.append("     |\n", style=STYLE_DIM)
            for i, r in enumerate(team_rows):
                is_last    = i == len(team_rows) - 1
                line_pfx   = "     |-- "
                body_pfx   = ("         " if is_last else "     |   ")
                _render_row(r, line_pfx=line_pfx, body_pfx=body_pfx)
                if not is_last:
                    out.append("     |\n", style=STYLE_DIM)

    out.append("\n")
    out.append(sep + "\n", style=STYLE_DIM)
    return out


def _tab_label(s: dict) -> str:
    """Build a tab title: project name + status dot."""
    project = s.get("project") or ""
    name    = Path(project).name if project else s["session_id"][:8]
    dot     = "●" if s["status"] == "live" else "○"
    return f" {dot} {name} "


def render_tab_bar(sessions: list[dict], selected: int) -> "Text":
    """Render horizontal tab bar across the top."""
    from rich.text import Text

    bar = Text()
    bar.append("  ")
    for i, s in enumerate(sessions):
        label = _tab_label(s)
        if i == selected:
            bar.append(label, style=STYLE_TAB_SEL)
        else:
            dot_style = STYLE_NEON if s["status"] == "live" else STYLE_DIM
            # Render the dot with status colour, rest dim
            dot     = "●" if s["status"] == "live" else "○"
            project = s.get("project") or ""
            name    = Path(project).name if project else s["session_id"][:8]
            bar.append(f" {dot}", style=dot_style)
            bar.append(f" {name} ", style=STYLE_TAB)
        if i < len(sessions) - 1:
            bar.append("│", style=STYLE_DIM)
    bar.append("\n")
    bar.append("  " + "─" * 76 + "\n", style=STYLE_DIM)
    return bar


def render_tabbed_view(sessions: list[dict], selected: int) -> "Text":
    """Render tab bar + selected session body."""
    from rich.text import Text

    out = Text()

    if not sessions:
        out.append("\n  no sessions found\n")
        return out

    # Clamp selection
    selected = max(0, min(selected, len(sessions) - 1))

    out.append_text(render_tab_bar(sessions, selected))
    out.append_text(_render_session_body(sessions[selected]))

    # Navigation hint
    out.append("\n  ")
    out.append("Tab", style=STYLE_KEY)
    out.append("/", style=STYLE_DIM)
    out.append("Shift+Tab", style=STYLE_KEY)
    out.append(" navigate  ", style=STYLE_DIM)
    out.append("1-9", style=STYLE_KEY)
    out.append(" jump  ", style=STYLE_DIM)
    out.append("q", style=STYLE_KEY)
    out.append(" quit\n", style=STYLE_DIM)

    return out


# ── Typer app ──────────────────────────────────────────────────────────────────

app = typer.Typer(name="observe", help="Session inspector.", add_completion=False)


@app.command("watch")
def watch_cmd():
    """Live tabbed view — updates on file changes."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    from rich.console import Console

    console  = Console()
    selected = [0]  # mutable container for closure access
    sessions_cache: list[dict] = []
    lock     = threading.Lock()
    timer: threading.Timer | None = None
    dirty    = threading.Event()

    def _scan_and_render():
        nonlocal sessions_cache
        sessions_cache = scan_sessions()
        return render_tabbed_view(sessions_cache, selected[0])

    def schedule_refresh():
        dirty.set()

    def debounced_refresh():
        nonlocal timer
        with lock:
            if timer is not None:
                timer.cancel()
            timer = threading.Timer(DEBOUNCE_S, schedule_refresh)
            timer.daemon = True
            timer.start()

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.is_directory:
                return
            debounced_refresh()

    observer = Observer()
    handler  = Handler()

    logs_dir = SUBAGENT_LOG.parent
    for watch_dir in (SESSIONS_DIR, PROJECTS_DIR, TEAMS_DIR, logs_dir):
        watch_dir.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(watch_dir), recursive=True)

    observer.start()

    # Save original terminal settings and switch to alternate buffer + raw mode
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Alternate screen buffer
        sys.stdout.write("\033[?1049h")  # enter alternate buffer
        sys.stdout.write("\033[?25l")    # hide cursor
        sys.stdout.flush()

        tty.setcbreak(fd)

        # Initial render
        dirty.set()

        while True:
            # Check for dirty flag (file changes or highlight expiry)
            if dirty.is_set():
                dirty.clear()
                output = _scan_and_render()
                sys.stdout.write("\033[H\033[2J")  # home + clear
                sys.stdout.flush()
                console.print(output, highlight=False)

                # Schedule refresh for highlight expiry
                now     = time.time()
                pending = [exp - now for exp in _highlight_until.values() if exp > now]
                if pending:
                    t = threading.Timer(min(pending) + 0.05, schedule_refresh)
                    t.daemon = True
                    t.start()

            # Poll for keyboard input (100ms timeout)
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)

                if ch == 'q' or ch == '\x03':  # q or Ctrl-C
                    break

                elif ch == '\t':  # Tab — next
                    if sessions_cache:
                        selected[0] = (selected[0] + 1) % len(sessions_cache)
                        dirty.set()

                elif ch == '\x1b':  # Escape sequence
                    # Read rest of escape sequence (non-blocking)
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        seq = sys.stdin.read(1)
                        if seq == '[':
                            if select.select([sys.stdin], [], [], 0.05)[0]:
                                code = sys.stdin.read(1)
                                if code == 'Z':  # Shift+Tab
                                    if sessions_cache:
                                        selected[0] = (selected[0] - 1) % len(sessions_cache)
                                        dirty.set()

                elif ch in '123456789':
                    idx = int(ch) - 1
                    if sessions_cache and idx < len(sessions_cache):
                        selected[0] = idx
                        dirty.set()

    finally:
        # Restore terminal state
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h")    # show cursor
        sys.stdout.write("\033[?1049l")  # leave alternate buffer
        sys.stdout.flush()
        observer.stop()
        observer.join()
