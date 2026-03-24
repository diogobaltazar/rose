import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from watchfiles import awatch

LOG_DIR = Path(os.environ.get("LOG_DIR", Path.home() / ".claude" / "logs"))
CONFIG_FILE = Path(os.environ.get("ROSE_CONFIG", Path.home() / ".config" / "rose" / "config.json"))


def _registered_projects() -> set[str] | None:
    """Return registered project paths, or None if no config exists (observe all)."""
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text())
        projects = data.get("projects", [])
        return {str(Path(p).resolve()) for p in projects} if projects else None
    except (json.JSONDecodeError, OSError):
        return None


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _derive_current_step(events_file: Path) -> str | None:
    stack = []
    try:
        with events_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                evt = event.get("event", "")
                if evt == "step.enter":
                    step = event.get("payload", {}).get("step") or event.get("step")
                    if step:
                        stack.append(step)
                elif evt == "step.exit":
                    if stack:
                        stack.pop()
    except OSError:
        pass
    return stack[-1] if stack else None


def _has_session_end(events_file: Path) -> bool:
    """Return True if events.jsonl contains a session.end event."""
    try:
        with events_file.open() as f:
            for line in f:
                try:
                    if json.loads(line.strip()).get("event") == "session.end":
                        return True
                except (json.JSONDecodeError, AttributeError):
                    continue
    except OSError:
        pass
    return False


def _load_session(session_dir: Path) -> dict | None:
    meta_file = session_dir / "meta.json"
    events_file = session_dir / "events.jsonl"
    if not meta_file.exists() or not events_file.exists():
        return None
    try:
        meta = json.loads(meta_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    # Derive status from events — avoids race with meta.json update on session end.
    status = "completed" if _has_session_end(events_file) else "in_progress"
    return {
        "session_id": meta.get("session_id", session_dir.name),
        "repository": meta.get("repository", "unknown"),
        "branch": meta.get("branch", "unknown"),
        "issue": meta.get("issue", None),
        "entry_point": meta.get("entry_point", None),
        "current_step": _derive_current_step(events_file),
        "outcome": meta.get("outcome", None),
        "started_at": meta.get("started_at", None),
        "status": status,
        "title": meta.get("title", None),
    }


def _scan_sessions() -> list[dict]:
    sessions = []
    if not LOG_DIR.exists():
        return sessions
    projects = _registered_projects()
    for session_dir in LOG_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        session = _load_session(session_dir)
        if not session:
            continue
        if projects is not None:
            repo = str(Path(session["repository"]).resolve())
            if repo not in projects:
                continue
        sessions.append(session)
    return sessions


@app.get("/sessions")
def get_sessions() -> list[dict]:
    return _scan_sessions()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json(_scan_sessions())

    async def watch_logs():
        async for changes in awatch(str(LOG_DIR)):
            for _change_type, path in changes:
                path = Path(path)
                if path.name not in ("events.jsonl", "meta.json"):
                    continue
                session_dir = path.parent
                session = _load_session(session_dir)
                if session:
                    await websocket.send_json(session)

    try:
        await watch_logs()
    except Exception:
        pass


@app.websocket("/ws/events/{session_id}")
async def event_stream(websocket: WebSocket, session_id: str):
    from fastapi import WebSocketDisconnect
    await websocket.accept()
    events_file = LOG_DIR / session_id / "events.jsonl"

    # Send all existing events
    if events_file.exists():
        with events_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        await websocket.send_text(line)
                    except Exception:
                        return

    # Watch for new lines
    last_size = events_file.stat().st_size if events_file.exists() else 0

    async def watch_new_lines():
        nonlocal last_size
        async for _ in awatch(str(events_file.parent)):
            if not events_file.exists():
                continue
            new_size = events_file.stat().st_size
            if new_size <= last_size:
                continue
            with events_file.open() as f:
                f.seek(last_size)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            await websocket.send_text(line)
                        except Exception:
                            return
            last_size = new_size

    try:
        await watch_new_lines()
    except Exception:
        pass
