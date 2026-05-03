"""
Calendar sync state — persists the mapping between task IDs and CalDAV event URLs.

iCloud's get_object_by_uid() is broken, so we maintain a local mapping of
task source IDs to their CalDAV resource URLs for all future operations.
"""

import json
import os
from pathlib import Path
from typing import Any

STATE_DIR = Path(os.environ.get("TOPGUN_CALENDAR_STATE", str(Path.home() / ".topgun" / "calendar")))
STATE_FILE = STATE_DIR / "state.json"


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {"sync_token": None, "calendar_url": None, "events": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"sync_token": None, "calendar_url": None, "events": {}}


def _write_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def get_sync_token() -> str | None:
    return _read_state().get("sync_token")


def set_sync_token(token: str) -> None:
    state = _read_state()
    state["sync_token"] = token
    _write_state(state)


def get_calendar_url() -> str | None:
    return _read_state().get("calendar_url")


def set_calendar_url(url: str) -> None:
    state = _read_state()
    state["calendar_url"] = url
    _write_state(state)


def get_event_mapping(task_id: str) -> dict | None:
    state = _read_state()
    return state.get("events", {}).get(task_id)


def set_event_mapping(task_id: str, event_url: str, event_uid: str,
                      scheduled_start: str, scheduled_end: str) -> None:
    state = _read_state()
    events = state.setdefault("events", {})
    events[task_id] = {
        "event_url": event_url,
        "event_uid": event_uid,
        "scheduled_start": scheduled_start,
        "scheduled_end": scheduled_end,
        "user_modified": False,
    }
    _write_state(state)


def mark_user_modified(task_id: str) -> None:
    state = _read_state()
    event = state.get("events", {}).get(task_id)
    if event:
        event["user_modified"] = True
        _write_state(state)


def remove_event_mapping(task_id: str) -> None:
    state = _read_state()
    state.get("events", {}).pop(task_id, None)
    _write_state(state)


def get_all_event_mappings() -> dict[str, dict]:
    return _read_state().get("events", {})


def get_full_state() -> dict:
    return _read_state()
