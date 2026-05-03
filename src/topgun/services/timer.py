"""
Timer service — manages time tracking events.

Extracted from cli/task.py so both the API and CLI can share this logic.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

TIMER_LOG = Path(os.environ.get("TOPGUN_TIMER_LOG", str(Path.home() / ".topgun" / "timer.jsonl")))


def append_event(event: str, task_id: str, task_title: str) -> dict:
    TIMER_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "task_id": task_id,
        "task_title": task_title,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with TIMER_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_events() -> list[dict]:
    if not TIMER_LOG.exists():
        return []
    events = []
    with TIMER_LOG.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def active_period() -> dict | None:
    last_start = None
    for e in read_events():
        if e["event"] == "start":
            last_start = e
        elif e["event"] == "stop":
            last_start = None
    return last_start


def elapsed_seconds(start_ts: str) -> float:
    t0 = datetime.fromisoformat(start_ts)
    return (datetime.now(timezone.utc) - t0).total_seconds()


def totals_by_task_id() -> dict[str, float]:
    totals: dict[str, float] = {}
    open_start: dict | None = None
    for e in read_events():
        if e["event"] == "start":
            open_start = e
        elif e["event"] == "stop" and open_start:
            t0 = datetime.fromisoformat(open_start["ts"])
            t1 = datetime.fromisoformat(e["ts"])
            tid = open_start["task_id"]
            totals[tid] = totals.get(tid, 0) + (t1 - t0).total_seconds()
            open_start = None
    if open_start:
        tid = open_start["task_id"]
        totals[tid] = totals.get(tid, 0) + elapsed_seconds(open_start["ts"])
    return totals


def intervals_by_task_id(task_id: str) -> list[dict]:
    intervals = []
    open_start: dict | None = None
    for e in read_events():
        if e["event"] == "start" and e["task_id"] == task_id:
            open_start = e
        elif e["event"] == "stop" and open_start and open_start["task_id"] == task_id:
            t0 = datetime.fromisoformat(open_start["ts"])
            t1 = datetime.fromisoformat(e["ts"])
            intervals.append({
                "start": open_start["ts"],
                "end": e["ts"],
                "duration_s": (t1 - t0).total_seconds(),
            })
            open_start = None
    if open_start:
        intervals.append({
            "start": open_start["ts"],
            "end": None,
            "duration_s": elapsed_seconds(open_start["ts"]),
        })
    return intervals


def start_timer(task_id: str, task_title: str) -> dict:
    active = active_period()
    if active:
        raise ValueError(
            f"Timer already running: {active['task_title']} "
            f"(started {active['ts']})"
        )
    return append_event("start", task_id, task_title)


def stop_timer() -> dict:
    active = active_period()
    if not active:
        raise ValueError("No timer running")
    record = append_event("stop", active["task_id"], active["task_title"])
    return {
        "task_id": active["task_id"],
        "task_title": active["task_title"],
        "started_at": active["ts"],
        "stopped_at": record["ts"],
        "elapsed_s": elapsed_seconds(active["ts"]),
    }


def timer_status() -> dict | None:
    active = active_period()
    if not active:
        return None
    return {
        "task_id": active["task_id"],
        "task_title": active["task_title"],
        "started_at": active["ts"],
        "elapsed_s": elapsed_seconds(active["ts"]),
    }
