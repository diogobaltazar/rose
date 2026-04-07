"""
rose-api — session data backend for rose-web.

Serves the same rich session data that the CLI's `rose observe watch` renders,
including agent metrics, token counts, costs, and subagent details.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from watchfiles import awatch

LOG_DIR = Path(os.environ.get("LOG_DIR", Path.home() / ".claude" / "logs"))
PROJECTS_DIR = Path(os.environ.get("PROJECTS_DIR", Path.home() / ".claude" / "projects"))
SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", Path.home() / ".claude" / "sessions"))
TEAMS_DIR = Path(os.environ.get("TEAMS_DIR", Path.home() / ".claude" / "teams"))
CONFIG_FILE = Path(os.environ.get("ROSE_CONFIG", Path.home() / ".config" / "rose" / "config.json"))
WEB_DIR = Path(__file__).parent.parent / "web"

STALE_THRESHOLD = 120  # seconds — transcript older than this is considered done

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
    """Map transcript stem → {pid, sessionId} for live sessions."""
    result = {}
    if not SESSIONS_DIR.exists():
        return result
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            pid = data.get("pid")
            sid = data.get("sessionId")
            cwd = data.get("cwd", "")
            started_ms = data.get("startedAt", 0)
        except (json.JSONDecodeError, OSError):
            continue
        if not pid or not cwd:
            continue
        # Inside Docker we can't check host PIDs; presence of the session file
        # is our best signal that the process is still running.
        started_s = started_ms / 1000
        project_dir = PROJECTS_DIR / _encode_cwd(cwd)
        if not project_dir.exists():
            continue
        for transcript in project_dir.glob("*.jsonl"):
            if transcript.stat().st_mtime >= started_s:
                result[transcript.stem] = {"pid": pid, "sessionId": sid}
                break
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

    return {
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

        jsonl_file = subagents_dir / f"agent-{agent_id}.jsonl"
        started_at = None
        ended_at = None
        tool_count = 0
        size_kb = None
        agent_cwd = None
        jsonl_mtime = None
        usage = _empty_usage()

        if jsonl_file.exists():
            st = jsonl_file.stat()
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


# Mount static files last so API routes take priority
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")
