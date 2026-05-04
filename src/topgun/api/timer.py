"""
Manual time tracking for intel documents — Google Drive JSONL backend.

Events appended to timers.jsonl: {uid, event: start|stop, ts: ISO8601}
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from deps import require_auth, get_storage

router = APIRouter(prefix="/timer", tags=["timer"])

TIMER_FILE = "timers.jsonl"
INTEL_FILE = "registry.jsonl"


def _intel_exists(client, uid: str) -> bool:
    docs = client.read_jsonl(INTEL_FILE)
    return any(d.get("uid") == uid for d in docs)


def _compute_status(events: list[dict]) -> dict[str, Any]:
    """Derive timer status from raw events for a single uid."""
    entries = []
    current_start: str | None = None

    for ev in events:
        if ev["event"] == "start":
            current_start = ev["ts"]
        elif ev["event"] == "stop" and current_start:
            started = datetime.fromisoformat(current_start)
            stopped = datetime.fromisoformat(ev["ts"])
            elapsed_s = round((stopped - started).total_seconds(), 1)
            entries.append({"start": current_start, "end": ev["ts"], "elapsed_s": elapsed_s})
            current_start = None

    total_s = sum(e["elapsed_s"] for e in entries)
    status = "running" if current_start else "stopped"

    if status == "running" and current_start:
        now = datetime.now(timezone.utc)
        started = datetime.fromisoformat(current_start)
        total_s += round((now - started).total_seconds(), 1)

    return {
        "status": status,
        "current_start": current_start,
        "entries": entries,
        "total_s": round(total_s, 1),
    }


@router.get("/{uid}")
def timer_status(uid: str, auth: dict | None = Depends(require_auth)) -> dict[str, Any]:
    client = get_storage(auth)
    all_events = client.read_jsonl(TIMER_FILE)
    events = [e for e in all_events if e.get("uid") == uid]
    return {"uid": uid, **_compute_status(events)}


@router.post("/{uid}/start")
def timer_start(uid: str, auth: dict | None = Depends(require_auth)) -> dict[str, Any]:
    client = get_storage(auth)

    if not _intel_exists(client, uid):
        raise HTTPException(status_code=404, detail="Intel document not found")

    all_events = client.read_jsonl(TIMER_FILE)
    uid_events = [e for e in all_events if e.get("uid") == uid]
    current = _compute_status(uid_events)

    if current["status"] == "running":
        raise HTTPException(status_code=409, detail="Timer already running")

    now = datetime.now(timezone.utc).isoformat()
    client.append_jsonl(TIMER_FILE, {"uid": uid, "event": "start", "ts": now})
    return {"uid": uid, "status": "running", "started_at": now}


@router.post("/{uid}/stop")
def timer_stop(uid: str, auth: dict | None = Depends(require_auth)) -> dict[str, Any]:
    client = get_storage(auth)

    all_events = client.read_jsonl(TIMER_FILE)
    uid_events = [e for e in all_events if e.get("uid") == uid]
    current = _compute_status(uid_events)

    if current["status"] != "running":
        raise HTTPException(status_code=409, detail="Timer not running")

    now = datetime.now(timezone.utc).isoformat()
    client.append_jsonl(TIMER_FILE, {"uid": uid, "event": "stop", "ts": now})

    started = datetime.fromisoformat(current["current_start"])
    stopped = datetime.fromisoformat(now)
    elapsed_s = round((stopped - started).total_seconds(), 1)

    return {
        "uid": uid,
        "status": "stopped",
        "elapsed_s": elapsed_s,
        "total_entries": len(current["entries"]) + 1,
    }
