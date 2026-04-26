"""
Unit tests for topgun.cli.timer.

Covers event log helpers (append, read, active period detection) and the
duration formatting utility. These are the core primitives that all four
subcommands (start, stop, status, report) depend on — if they break, every
consumer produces wrong output or loses data.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from topgun.cli.timer import (
    _append_event,
    _active_period,
    _fmt_duration,
    _read_events,
    TIMER_LOG,
)


@pytest.fixture(autouse=True)
def isolated_timer_log(tmp_path, monkeypatch):
    """
    Redirect TIMER_LOG to a temp file for every test.

    Without this, tests would corrupt the real ~/.topgun/timer.jsonl.
    Each test gets a clean slate; no ordering dependency.
    """
    log = tmp_path / "timer.jsonl"
    monkeypatch.setattr("topgun.cli.timer.TIMER_LOG", log)
    return log


# ── _fmt_duration ─────────────────────────────────────────────────────────────

def test_fmt_duration_seconds():
    """Sub-minute durations must show minutes and seconds, not just seconds.

    A pure-seconds format would be confusing for values like 90s (reads as
    1m 30s in human terms). The format must always anchor to minutes.
    """
    assert _fmt_duration(45) == "0m 45s"


def test_fmt_duration_minutes():
    """Values under an hour must show minutes and seconds only."""
    assert _fmt_duration(125) == "2m 05s"


def test_fmt_duration_hours():
    """Values over an hour must show hours and minutes, dropping seconds.

    Report rows would be too wide if seconds were included for multi-hour tasks.
    """
    assert _fmt_duration(3_661) == "1h 01m"


# ── _append_event / _read_events ─────────────────────────────────────────────

def test_append_and_read_single_event(isolated_timer_log):
    """
    A written event must be readable back with identical fields.

    This validates the round-trip guarantee of the append-only log.
    If the schema drifts between write and read, report() and status()
    will silently drop or misread past periods.
    """
    _append_event("start", "github:owner/repo#1", "Fix auth bug")
    events = _read_events()
    assert len(events) == 1
    e = events[0]
    assert e["event"] == "start"
    assert e["task_id"] == "github:owner/repo#1"
    assert e["task_title"] == "Fix auth bug"
    assert "ts" in e


def test_append_multiple_events_preserves_order(isolated_timer_log):
    """
    Events must be returned in append order.

    report() relies on chronological ordering to pair start/stop events
    correctly. Out-of-order reads would produce wrong durations.
    """
    _append_event("start", "github:owner/repo#1", "Task A")
    _append_event("stop",  "github:owner/repo#1", "Task A")
    _append_event("start", "github:owner/repo#2", "Task B")
    events = _read_events()
    assert [e["event"] for e in events] == ["start", "stop", "start"]


def test_read_events_tolerates_empty_log(isolated_timer_log):
    """Empty log must return an empty list, not raise an exception."""
    assert _read_events() == []


# ── _active_period ────────────────────────────────────────────────────────────

def test_active_period_none_when_no_events(isolated_timer_log):
    """No events → no active period."""
    assert _active_period() is None


def test_active_period_detected_after_start(isolated_timer_log):
    """A start event with no following stop must be detected as the active period."""
    _append_event("start", "github:owner/repo#1", "Task A")
    active = _active_period()
    assert active is not None
    assert active["task_id"] == "github:owner/repo#1"


def test_active_period_cleared_after_stop(isolated_timer_log):
    """
    A start followed by a stop must leave no active period.

    This guards against the timer falsely showing as running after stop()
    is called, which would block a subsequent start().
    """
    _append_event("start", "github:owner/repo#1", "Task A")
    _append_event("stop",  "github:owner/repo#1", "Task A")
    assert _active_period() is None


def test_active_period_after_two_complete_cycles(isolated_timer_log):
    """
    Two full start/stop cycles followed by a third start must return the third task.

    Validates that _active_period() tracks the latest open window, not the
    first one ever written.
    """
    _append_event("start", "github:owner/repo#1", "Task A")
    _append_event("stop",  "github:owner/repo#1", "Task A")
    _append_event("start", "github:owner/repo#2", "Task B")
    _append_event("stop",  "github:owner/repo#2", "Task B")
    _append_event("start", "github:owner/repo#3", "Task C")
    active = _active_period()
    assert active is not None
    assert active["task_id"] == "github:owner/repo#3"
