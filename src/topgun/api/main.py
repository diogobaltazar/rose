"""
topgun-api — session data backend for topgun-web.

Serves the same rich session data that the CLI's `topgun observe watch` renders,
including agent metrics, token counts, costs, and subagent details.

Also serves federated backlog data from configured GitHub repos and Obsidian vaults.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from watchfiles import awatch

LOG_DIR = Path(os.environ.get("LOG_DIR", Path.home() / ".claude" / "logs"))
PROJECTS_DIR = Path(os.environ.get("PROJECTS_DIR", Path.home() / ".claude" / "projects"))
SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", Path.home() / ".claude" / "sessions"))
TEAMS_DIR = Path(os.environ.get("TEAMS_DIR", Path.home() / ".claude" / "teams"))
CONFIG_FILE = Path(os.environ.get("TOPGUN_CONFIG", Path.home() / ".config" / "topgun" / "config.json"))
WEB_DIR = Path(__file__).parent.parent / "web"

STALE_THRESHOLD = 120  # seconds — transcript older than this is considered done

# ── Transcript read cache ─────────────────────────────────────────────────────
#
# _read_transcript() parses JSONL line-by-line. With hundreds of sessions on
# disk this becomes the dominant cost of every _scan_sessions() call, which is
# invoked synchronously inside the WebSocket handler — blocking the event loop
# before the initial payload is sent to the browser.
#
# The cache maps an absolute Path to a (mtime, result) tuple. Before parsing,
# _read_transcript() checks whether the file's current mtime matches the cached
# value. A cache hit returns the stored dict immediately; a cache miss (new
# file or mtime changed) parses the file and updates the entry. Live sessions
# receive a cache miss on each refresh because their mtime advances with every
# appended message, which is exactly the desired behaviour. Done sessions are
# parsed exactly once.
#
# The cache is module-level and lives for the lifetime of the API process.
# It is safe to grow without bound in practice: the number of sessions a user
# accumulates is bounded by disk space, and each cached entry is a small dict.
#
# _subagent_cache stores only the file-derived metrics (timestamps, tool count,
# token usage, size). Status determination (live/done) depends on dynamic
# inputs applied after the cache lookup, not stored in it.
_transcript_cache: dict[Path, tuple[float, dict]] = {}
_subagent_cache:   dict[Path, tuple[float, dict]] = {}

# ── Pricing ──────────────────────────────────────────────────────────────────

FALLBACK_PRICING = {
    "input": 3.0,
    "output": 15.0,
    "cache_write": 3.75,
    "cache_read": 0.30,
}


def _usd_for_usage(usage: dict, model: str | None) -> float:
    rates = FALLBACK_PRICING
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cw = usage.get("cache_creation_input_tokens", 0)
    cr = usage.get("cache_read_input_tokens", 0)
    return (
        inp * rates["input"] / 1_000_000
        + out * rates["output"] / 1_000_000
        + cw * rates["cache_write"] / 1_000_000
        + cr * rates["cache_read"] / 1_000_000
    )


# ── Formatting helpers ───────────────────────────────────────────────────────


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
    cleaned = re.sub(r"<[^>]+/>", "", cleaned)
    return cleaned.strip()


# ── Config ───────────────────────────────────────────────────────────────────


def _registered_projects() -> set[str] | None:
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text())
        projects = data.get("projects", [])
        return {str(Path(p).resolve()) for p in projects} if projects else None
    except (json.JSONDecodeError, OSError):
        return None


# ── Session file helpers ─────────────────────────────────────────────────────


def _encode_cwd(cwd: str) -> str:
    return cwd.replace("/", "-")


def _live_transcripts() -> dict[str, dict]:
    """Map session-id → {pid, sessionId} for every session whose file is present.

    Inside Docker the API cannot call os.kill() to verify host PIDs, so the
    presence of a session file in SESSIONS_DIR is used as the liveness signal.

    Previous implementation used glob() to find the first transcript in the
    project directory whose mtime was >= the session start time. Because glob()
    returns files in arbitrary filesystem order, it frequently identified the
    wrong transcript as belonging to the live session — causing the actual
    current session to appear as "done" in the UI.

    The session file already contains the sessionId, which equals the transcript
    filename (without the .jsonl extension). We look up the transcript directly
    by path, eliminating the ambiguity. If the transcript does not yet exist
    (session just started), we still register the session so it appears in the
    UI immediately via the SESSIONS_DIR fallback in _scan_sessions().
    """
    result = {}
    if not SESSIONS_DIR.exists():
        return result
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            pid = data.get("pid")
            sid = data.get("sessionId")
            cwd = data.get("cwd", "")
        except (json.JSONDecodeError, OSError):
            continue
        if not pid or not sid or not cwd:
            continue
        project_dir = PROJECTS_DIR / _encode_cwd(cwd)
        if not project_dir.exists():
            continue
        result[sid] = {"pid": pid, "sessionId": sid}
    return result


# ── Team config ──────────────────────────────────────────────────────────────


def _read_team_config(session_id: str) -> dict | None:
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


def _team_member_agent_ids(team_config: dict) -> set[str]:
    lead_id = team_config.get("leadAgentId", "")
    return {
        m["agentId"]
        for m in team_config.get("members", [])
        if m.get("agentId") != lead_id
    }


def _team_lead_type(team_config: dict) -> str | None:
    lead_id = team_config.get("leadAgentId", "")
    for m in team_config.get("members", []):
        if m.get("agentId") == lead_id:
            return m.get("agentType")
    return None


# ── Hook logs ────────────────────────────────────────────────────────────────


def _read_subagent_hook_states() -> dict[str, str]:
    log_file = LOG_DIR / "subagent-events.jsonl"
    states: dict[str, str] = {}
    if not log_file.exists():
        return states
    try:
        with log_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hook = entry.get("hook", "")
                payload = entry.get("payload", {})
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


def _read_shutdown_requests() -> dict[str, list[str]]:
    log_file = LOG_DIR / "message-events.jsonl"
    shutdowns: dict[str, list[str]] = {}
    if not log_file.exists():
        return shutdowns
    try:
        with log_file.open() as f:
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


# ── Transcript reading ───────────────────────────────────────────────────────


def _empty_usage() -> dict:
    return {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "usd": 0.0}


def _accumulate_usage(entry: dict, totals: dict) -> None:
    msg = entry.get("message", {})
    usage = msg.get("usage")
    if not usage:
        return
    model = msg.get("model") or entry.get("model")
    if model == "<synthetic>":
        model = None
    totals["input"] += usage.get("input_tokens", 0)
    totals["output"] += usage.get("output_tokens", 0)
    totals["cache_write"] += usage.get("cache_creation_input_tokens", 0)
    totals["cache_read"] += usage.get("cache_read_input_tokens", 0)
    totals["usd"] += _usd_for_usage(usage, model)


def _read_transcript(path: Path) -> dict:
    # Cache check — return immediately if the file has not changed since last parse.
    # Transcripts are append-only JSONL files: a changed mtime always means new
    # content. Done sessions are never appended to, so they are parsed exactly once.
    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        current_mtime = None

    if current_mtime is not None:
        cached = _transcript_cache.get(path)
        if cached is not None and cached[0] == current_mtime:
            return cached[1]

    title = None
    branch = None
    cwd = None
    started_at = None
    ended_at = None
    tool_count = 0
    usage = _empty_usage()
    agent_tool_use: dict[str, str] = {}
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

                if etype == "user":
                    msg = entry.get("message", {})
                    if msg.get("role") == "user":
                        cwd = entry.get("cwd") or cwd
                        branch = entry.get("gitBranch") or branch
                        if title is None:
                            content = msg.get("content", "")
                            if isinstance(content, str):
                                cleaned = _strip_tags(content)
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
                            1
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "tool_use"
                        )
                    _accumulate_usage(entry, usage)

                elif etype == "progress":
                    data = entry.get("data", {})
                    if data.get("type") == "agent_progress":
                        agent_id = data.get("agentId")
                        parent_tuid = entry.get("parentToolUseID")
                        if agent_id and parent_tuid:
                            agent_tool_use[agent_id] = parent_tuid

    except OSError:
        pass

    total_tokens = usage["input"] + usage["output"] + usage["cache_write"] + usage["cache_read"]

    result = {
        "cwd": cwd,
        "branch": branch,
        "started_at": started_at,
        "ended_at": ended_at,
        "title": title,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "tool_count": tool_count,
        "tokens": total_tokens,
        "usd": usage["usd"],
        "agent_tool_use": agent_tool_use,
        "completed_tool_uses": completed_tool_uses,
    }

    if current_mtime is not None:
        _transcript_cache[path] = (current_mtime, result)

    return result


def _read_subagents(
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

        agent_type = meta.get("agentType", "unknown")
        description = meta.get("description", "")

        jsonl_file  = subagents_dir / f"agent-{agent_id}.jsonl"
        started_at  = None
        ended_at    = None
        tool_count  = 0
        size_kb     = None
        agent_cwd   = None
        jsonl_mtime = None
        usage       = _empty_usage()

        if jsonl_file.exists():
            st          = jsonl_file.stat()
            jsonl_mtime = st.st_mtime

            # Cache check — subagent JSONL files are append-only. If mtime is
            # unchanged the previously parsed metrics are still valid.
            cached_sub = _subagent_cache.get(jsonl_file)
            if cached_sub is not None and cached_sub[0] == jsonl_mtime:
                m          = cached_sub[1]
                started_at = m["started_at"]
                ended_at   = m["ended_at"]
                tool_count = m["tool_count"]
                size_kb    = m["size_kb"]
                agent_cwd  = m["agent_cwd"]
                usage      = m["usage"]
            else:
                size_kb = round(st.st_size / 1024, 1)
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
                                        1
                                        for b in content
                                        if isinstance(b, dict) and b.get("type") == "tool_use"
                                    )
                                _accumulate_usage(entry, usage)
                except OSError:
                    pass
                _subagent_cache[jsonl_file] = (jsonl_mtime, {
                    "started_at": started_at,
                    "ended_at":   ended_at,
                    "tool_count": tool_count,
                    "size_kb":    size_kb,
                    "agent_cwd":  agent_cwd,
                    "usage":      usage,
                })

        tool_use_id = agent_tool_use.get(agent_id, "")
        tool_result_done = bool(tool_use_id and tool_use_id in completed_tool_uses)
        stale = jsonl_mtime is not None and (time.time() - jsonl_mtime) > STALE_THRESHOLD

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

        agents.append(
            {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "description": description,
                "started_at": started_at,
                "ended_at": ended_at,
                "size_kb": size_kb,
                "tool_count": tool_count,
                "tokens": total_tokens,
                "usd": usage["usd"],
                "duration": duration,
                "status": status,
                "cwd": agent_cwd,
            }
        )

    agents.sort(key=lambda a: a["started_at"] or "")
    return agents


# ── Session meta ─────────────────────────────────────────────────────────────


def _read_session_meta(session_dir: Path) -> dict:
    try:
        return json.loads((session_dir / "meta.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


# ── Full session scan ────────────────────────────────────────────────────────


def _scan_sessions() -> list[dict]:
    live = _live_transcripts()
    hook_states = _read_subagent_hook_states()
    shutdown_requests = _read_shutdown_requests()
    sessions = []
    matched_pids = set()

    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            for transcript in project_dir.glob("*.jsonl"):
                session_id = transcript.stem
                info = _read_transcript(transcript)

                if session_id in live:
                    status = "live"
                    pid = live[session_id]["pid"]
                    process_sid = live[session_id]["sessionId"]
                    matched_pids.add(pid)
                else:
                    status = "done"
                    pid = None
                    process_sid = None

                session_dir = transcript.parent / session_id
                agents = _read_subagents(
                    session_dir,
                    info["agent_tool_use"],
                    info["completed_tool_uses"],
                    status == "live",
                    hook_states,
                    shutdown_requests,
                )
                team_config = _read_team_config(session_id) if status == "live" else None
                session_meta = _read_session_meta(session_dir)

                # Session-wide duration
                all_starts = [s for s in [info["started_at"]] + [a["started_at"] for a in agents] if s]
                all_ends = [e for e in [info["ended_at"]] + [a["ended_at"] for a in agents] if e]
                duration = None
                if all_starts and all_ends:
                    try:
                        t0 = datetime.fromisoformat(min(all_starts).replace("Z", "+00:00"))
                        t1 = datetime.fromisoformat(max(all_ends).replace("Z", "+00:00"))
                        duration = (t1 - t0).total_seconds()
                    except Exception:
                        pass

                total_kb = round((info["size_kb"] or 0) + sum((a["size_kb"] or 0) for a in agents), 1)
                total_tools = info["tool_count"] + sum(a["tool_count"] for a in agents)
                total_tokens = info["tokens"] + sum(a["tokens"] for a in agents)
                total_usd = info["usd"] + sum(a["usd"] for a in agents)

                own_duration = None
                if info["started_at"] and info["ended_at"]:
                    try:
                        t0 = datetime.fromisoformat(info["started_at"].replace("Z", "+00:00"))
                        t1 = datetime.fromisoformat(info["ended_at"].replace("Z", "+00:00"))
                        own_duration = (t1 - t0).total_seconds()
                    except Exception:
                        pass

                # Derive project from cwd (best effort without git)
                project = info["cwd"] or ""

                sessions.append(
                    {
                        "session_id": session_id,
                        "process_sid": process_sid,
                        "pid": pid,
                        "status": status,
                        "project": project,
                        "branch": info["branch"],
                        "started_at": info["started_at"],
                        "title": info["title"],
                        "duration": duration,
                        "total_kb": total_kb,
                        "total_tools": total_tools,
                        "total_tokens": total_tokens,
                        "total_usd": total_usd,
                        "own_kb": round(info["size_kb"] or 0, 1),
                        "own_tools": info["tool_count"],
                        "own_tokens": info["tokens"],
                        "own_usd": info["usd"],
                        "own_duration": own_duration,
                        "agents": agents,
                        "team_config": team_config,
                        "meta": session_meta,
                    }
                )

    # Also pick up sessions visible only via /sessions/*.json (no transcript yet)
    if SESSIONS_DIR.exists():
        for f in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                pid = data.get("pid")
                sid = data.get("sessionId")
                cwd = data.get("cwd", "")
                ms = data.get("startedAt", 0)
            except (json.JSONDecodeError, OSError):
                continue
            if not pid or pid in matched_pids:
                continue
            sessions.append(
                {
                    "session_id": sid,
                    "process_sid": None,
                    "pid": pid,
                    "status": "live",
                    "project": cwd,
                    "branch": None,
                    "started_at": datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(),
                    "title": None,
                    "duration": None,
                    "total_kb": None,
                    "total_tools": 0,
                    "total_tokens": 0,
                    "total_usd": 0.0,
                    "own_kb": None,
                    "own_tools": 0,
                    "own_tokens": 0,
                    "own_usd": 0.0,
                    "own_duration": None,
                    "agents": [],
                    "team_config": None,
                    "meta": {},
                }
            )

    sessions.sort(key=lambda s: s["started_at"] or "", reverse=True)
    return sessions


# ── FastAPI app ──────────────────────────────────────────────────────────────

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/sessions")
def get_sessions() -> list[dict]:
    return _scan_sessions()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json(_scan_sessions())

    # Build watch paths — only watch directories that exist
    watch_paths = []
    for d in (LOG_DIR, PROJECTS_DIR, SESSIONS_DIR, TEAMS_DIR):
        if d.exists():
            watch_paths.append(str(d))

    if not watch_paths:
        # Nothing to watch — keep connection alive
        try:
            while True:
                await asyncio.sleep(60)
        except Exception:
            return

    async def watch_changes():
        async for changes in awatch(*watch_paths):
            # Any change in watched dirs triggers a full rescan
            try:
                await websocket.send_json(_scan_sessions())
            except Exception:
                return

    try:
        await watch_changes()
    except Exception:
        pass


# ── Backlog — config ─────────────────────────────────────────────────────────

BACKLOG_CACHE_TTL = int(os.environ.get("BACKLOG_CACHE_TTL", "60"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER_HOME = Path(os.environ.get("USER_HOME", str(Path.home())))

_PRIORITY_EMOJIS: dict[str, str] = {"⏫": "high", "🔼": "medium", "🔽": "low"}
_TASK_RE = re.compile(r"^- \[([ x])\] (.+)$")
_DUE_RE = re.compile(r"📅 (\d{4}-\d{2}-\d{2})")
_SCHED_RE = re.compile(r"⏳ (\d{4}-\d{2}-\d{2})")
_DONE_RE = re.compile(r"✅ (\d{4}-\d{2}-\d{2})")
_RECUR_RE = re.compile(r"🔁 (every [^\s⏫🔼🔽📅⏳✅\n]+)")

# ── Backlog — in-memory cache ────────────────────────────────────────────────

_backlog_cache: list[dict] = []
_backlog_cache_time: float = 0.0
_backlog_cache_lock = asyncio.Lock()
_backlog_ws_clients: set[WebSocket] = set()


# ── Backlog — helpers ────────────────────────────────────────────────────────


def _backlog_sources() -> list[dict]:
    """Read configured backlog sources from the topgun config file."""
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        return cfg.get("backlog", {}).get("sources", [])
    except (OSError, json.JSONDecodeError):
        return []


def _resolve_vault_path(path_str: str) -> Path:
    """Resolve a vault path, replacing ~ with the mounted user home.

    Also remaps absolute host paths that contain .topgun — e.g.
    /Users/someone/.topgun/backlog/... → USER_HOME/.topgun/backlog/...
    """
    if path_str.startswith("~/"):
        return USER_HOME / path_str[2:]
    if path_str.startswith("~"):
        return USER_HOME / path_str[1:]
    p = Path(path_str)
    if p.is_absolute() and ".topgun" in p.parts:
        idx = p.parts.index(".topgun")
        rest = Path(*p.parts[idx + 1:]) if idx + 1 < len(p.parts) else Path(".")
        return USER_HOME / ".topgun" / rest
    return p


def _parse_body_section(body: str, section: str) -> str:
    """Extract the text content of a ## Section from a GitHub issue body."""
    pattern = rf"## {re.escape(section)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, body, re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_github_issue(issue: dict, source: dict) -> dict:
    """Normalise a raw GitHub API issue into the unified backlog item shape."""
    body = issue.get("body") or ""
    labels = {lbl["name"] for lbl in (issue.get("labels") or [])}
    priority = next((v for k, v in {"priority:high": "high", "priority:medium": "medium", "priority:low": "low"}.items() if k in labels), None)

    ac_raw = _parse_body_section(body, "Acceptance Criteria")
    ac = [line.lstrip("- [ ]").lstrip("- [x]").strip() for line in ac_raw.splitlines() if line.strip().startswith("- ")]

    deps_raw = _parse_body_section(body, "Dependencies")
    deps = [w.strip() for w in deps_raw.splitlines() if w.strip() and w.strip() != "none"]

    return {
        "id": f"gh:{source['repo']}#{issue['number']}",
        "source_type": "github",
        "source_repo": source["repo"],
        "source_description": source.get("description", ""),
        "number": issue["number"],
        "title": issue.get("title", ""),
        "state": issue.get("state", "open"),
        "created_at": issue.get("created_at"),
        "closed_at": issue.get("closed_at"),
        "priority": priority,
        "best_before": _parse_body_section(body, "Best Before") or None,
        "must_before": _parse_body_section(body, "Must Before") or None,
        "about": _parse_body_section(body, "About") or None,
        "motivation": _parse_body_section(body, "Motivation") or None,
        "acceptance_criteria": ac,
        "dependencies": deps,
        "url": issue.get("html_url"),
        "file": None,
        "line": None,
    }


def _parse_obsidian_file(file_path: Path, vault_root: Path, source: dict) -> list[dict]:
    """Extract Tasks-plugin tasks from a single markdown file."""
    items = []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return items

    rel_path = str(file_path.relative_to(vault_root))

    for lineno, line in enumerate(lines, start=1):
        m = _TASK_RE.match(line.strip())
        if not m:
            continue

        state_char, rest = m.group(1), m.group(2)
        state = "closed" if state_char == "x" else "open"

        priority = next((v for emoji, v in _PRIORITY_EMOJIS.items() if emoji in rest), None)
        must_before = _DUE_RE.search(rest)
        best_before = _SCHED_RE.search(rest)
        closed_at = _DONE_RE.search(rest)

        # Strip metadata emojis from title
        title = rest
        for pat in (_DUE_RE, _SCHED_RE, _DONE_RE, _RECUR_RE):
            title = pat.sub("", title)
        for emoji in list(_PRIORITY_EMOJIS) + ["🔁"]:
            title = title.replace(emoji, "")
        title = title.strip()

        items.append({
            "id": f"obsidian:{rel_path}#L{lineno}",
            "source_type": "obsidian",
            "source_repo": None,
            "source_description": source.get("description", ""),
            "number": None,
            "title": title,
            "state": state,
            "created_at": None,
            "closed_at": closed_at.group(1) if closed_at else None,
            "priority": priority,
            "best_before": best_before.group(1) if best_before else None,
            "must_before": must_before.group(1) if must_before else None,
            "about": None,
            "motivation": None,
            "acceptance_criteria": [],
            "dependencies": [],
            "url": None,
            "file": rel_path,
            "line": lineno,
        })

    return items


async def _fetch_github_source(source: dict, *, search: str | None = None) -> list[dict]:
    """Fetch issues from a GitHub repo via the REST API.

    When search is provided, uses the GitHub Search API to filter by keyword.
    Otherwise lists all issues.
    """
    repo = source["repo"]
    headers: dict[str, str] = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    items: list[dict] = []

    if search:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                r = await client.get(
                    "https://api.github.com/search/issues",
                    headers=headers,
                    params={
                        "q": f"{search} repo:{repo} is:issue",
                        "per_page": 50,
                    },
                )
                r.raise_for_status()
            except Exception:
                return items
            data = r.json()
            for issue in data.get("items", []):
                if "pull_request" not in issue:
                    items.append(_parse_github_issue(issue, source))
        return items

    page = 1
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                r = await client.get(
                    f"https://api.github.com/repos/{repo}/issues",
                    headers=headers,
                    params={"state": "all", "per_page": 100, "page": page},
                )
                r.raise_for_status()
            except Exception:
                break
            batch = r.json()
            if not batch:
                break
            for issue in batch:
                if "pull_request" not in issue:
                    items.append(_parse_github_issue(issue, source))
            if len(batch) < 100:
                break
            page += 1
    return items


def _fetch_obsidian_source(source: dict) -> list[dict]:
    """Read all Tasks-plugin tasks from an Obsidian vault."""
    vault_root = _resolve_vault_path(source["path"])
    if not vault_root.exists():
        return []
    items: list[dict] = []
    for md_file in vault_root.rglob("*.md"):
        items.extend(_parse_obsidian_file(md_file, vault_root, source))
    return items


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_SORT_FIELDS = {"title", "priority", "due", "scheduled", "source", "state", "created_at"}


def _sort_backlog(items: list[dict], sort: str, order: str) -> list[dict]:
    reverse = order == "desc"
    if sort == "priority":
        key = lambda x: (_PRIORITY_ORDER.get(x.get("priority") or "", 3), x.get("must_before") or "9999")
    elif sort == "due":
        key = lambda x: x.get("must_before") or "9999"
    elif sort == "scheduled":
        key = lambda x: x.get("best_before") or "9999"
    elif sort == "title":
        key = lambda x: (x.get("title") or "").lower()
    elif sort == "source":
        key = lambda x: x.get("source_repo") or ""
    elif sort == "state":
        key = lambda x: x.get("state") or ""
    elif sort == "created_at":
        key = lambda x: x.get("created_at") or ""
    else:
        key = lambda x: x.get("created_at") or ""
    return sorted(items, key=key, reverse=reverse)


async def _build_backlog(
    *,
    search: str | None = None,
    sort: str | None = None,
    order: str = "asc",
    status: str | None = None,
) -> list[dict]:
    """Fetch from all configured sources and return a unified item list."""
    sources = _backlog_sources()
    all_items: list[dict] = []

    github_tasks = [_fetch_github_source(s, search=search) for s in sources if s.get("type") == "github"]
    github_results = await asyncio.gather(*github_tasks, return_exceptions=True)
    for result in github_results:
        if isinstance(result, list):
            all_items.extend(result)

    for s in sources:
        if s.get("type") == "obsidian":
            items = _fetch_obsidian_source(s)
            if search:
                kw = search.lower()
                items = [i for i in items if kw in (i.get("title") or "").lower() or kw in (i.get("about") or "").lower()]
            all_items.extend(items)

    if status:
        statuses = {s.strip() for s in status.split(",")}
        all_items = [i for i in all_items if i.get("state") in statuses]

    if sort and sort in _SORT_FIELDS:
        all_items = _sort_backlog(all_items, sort, order)
    else:
        all_items.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return all_items


async def _refresh_and_broadcast() -> None:
    """Rebuild cache and push to all connected WebSocket clients."""
    global _backlog_cache, _backlog_cache_time
    items = await _build_backlog()
    async with _backlog_cache_lock:
        _backlog_cache = items
        _backlog_cache_time = time.time()
    dead: set[WebSocket] = set()
    for ws in list(_backlog_ws_clients):
        try:
            await ws.send_json(items)
        except Exception:
            dead.add(ws)
    _backlog_ws_clients.difference_update(dead)


async def _backlog_refresh_loop() -> None:
    """Background task: refresh the backlog cache every BACKLOG_CACHE_TTL seconds."""
    while True:
        try:
            await _refresh_and_broadcast()
        except Exception:
            pass
        await asyncio.sleep(BACKLOG_CACHE_TTL)


# ── Backlog — endpoints ──────────────────────────────────────────────────────


@app.on_event("startup")
async def _startup_backlog() -> None:
    asyncio.create_task(_backlog_refresh_loop())


@app.get("/backlog")
async def get_backlog(
    search: str | None = None,
    sort: str | None = None,
    order: str = "asc",
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Return backlog items with optional filtering and sorting.

    Query params:
      search — keyword filter (GitHub search API + Obsidian substring)
      sort   — field name: title, priority, due, scheduled, source, state, created_at
      order  — asc or desc (default asc)
      status — comma-separated: open, closed (default: all)
    """
    if search or sort or status:
        return await _build_backlog(search=search, sort=sort, order=order, status=status)
    if not _backlog_cache:
        await _refresh_and_broadcast()
    return _backlog_cache


@app.post("/backlog/refresh")
async def post_backlog_refresh() -> dict[str, str]:
    """Trigger an immediate cache refresh and push to WebSocket clients."""
    await _refresh_and_broadcast()
    return {"status": "ok", "items": len(_backlog_cache)}


@app.websocket("/backlog/ws")
async def backlog_websocket(websocket: WebSocket) -> None:
    """WebSocket: sends current cache on connect, then pushes on every refresh."""
    await websocket.accept()
    _backlog_ws_clients.add(websocket)
    try:
        await websocket.send_json(_backlog_cache)
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except Exception:
        pass
    finally:
        _backlog_ws_clients.discard(websocket)


# ── Timer endpoints ─────────────────────────────────────────────────────────

from topgun.services.timer import (
    timer_status as _svc_timer_status,
    start_timer as _svc_start_timer,
    stop_timer as _svc_stop_timer,
)


@app.get("/timer/status")
def api_timer_status() -> dict[str, Any]:
    result = _svc_timer_status()
    return result or {"running": False}


@app.post("/timer/start")
def api_timer_start(body: dict) -> dict[str, Any]:
    task_id = body.get("task_id", "")
    task_title = body.get("task_title", "")
    if not task_id:
        return {"error": "task_id required"}
    try:
        record = _svc_start_timer(task_id, task_title)
        return {"status": "started", **record}
    except ValueError as e:
        return {"error": str(e)}


@app.post("/timer/stop")
def api_timer_stop() -> dict[str, Any]:
    try:
        return _svc_stop_timer()
    except ValueError as e:
        return {"error": str(e)}


# ── Task mutation endpoints ─────────────────────────────────────────────────

from topgun.services.tasks import close_task as _svc_close_task


@app.post("/tasks/{task_id:path}/close")
def api_close_task(task_id: str) -> dict[str, Any]:
    success = _svc_close_task(task_id)
    if success:
        return {"status": "closed", "task_id": task_id}
    return {"error": f"Failed to close task: {task_id}"}


# ── Calendar endpoints ──────────────────────────────────────────────────────

from topgun.services.calendar import CalendarService


def _get_calendar_service() -> CalendarService:
    svc = CalendarService()
    svc.connect()
    svc.get_or_create_calendar()
    return svc


@app.get("/calendar/status")
def api_calendar_status() -> dict[str, Any]:
    svc = CalendarService()
    connected = svc.connect()
    if connected:
        svc.get_or_create_calendar()
    return {**svc.get_status(), "connected": connected}


@app.post("/calendar/sync")
def api_calendar_sync() -> dict[str, Any]:
    svc = _get_calendar_service()
    result = svc.sync()
    return {
        "new_token": result.new_token,
        "user_modified": result.user_modified,
        "deleted": result.deleted,
        "unchanged": result.unchanged,
    }


@app.post("/calendar/schedule")
async def api_calendar_schedule() -> dict[str, Any]:
    svc = _get_calendar_service()
    items = await _build_backlog(status="open")
    result = svc.schedule_and_push(items)
    return {
        "scheduled": [
            {"task_id": s.task_id, "title": s.task_title,
             "start": s.start.isoformat(), "end": s.end.isoformat()}
            for s in result.scheduled
        ],
        "unschedulable": result.unschedulable,
    }


@app.get("/calendar/slots")
def api_calendar_slots(
    duration: int = 60,
    after: str | None = None,
) -> list[dict[str, str]]:
    import datetime as dt
    svc = _get_calendar_service()
    after_dt = dt.datetime.fromisoformat(after) if after else None
    slots = svc.find_available_slots(duration, after=after_dt)
    return [{"start": s.start.isoformat(), "end": s.end.isoformat()} for s in slots]


# Mount static files last so API routes take priority
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
