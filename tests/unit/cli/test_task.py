"""
Unit tests for topgun.cli.task.

Covers UID generation, event log helpers, time aggregation, and interval
extraction. These are the primitives that list, show, start, stop, and status
all depend on.
"""

import json
from pathlib import Path

import pytest

from topgun.cli.task import (
    _append_event,
    _active_period,
    _fmt_duration,
    _read_events,
    _totals_by_task_id,
    _intervals_by_task_id,
    _parse_filter,
    _slugify,
    _write_obsidian_task,
    TIMER_LOG,
)
from topgun.cli.timer_match import _uid


@pytest.fixture(autouse=True)
def isolated_timer_log(tmp_path, monkeypatch):
    log = tmp_path / "timer.jsonl"
    monkeypatch.setattr("topgun.cli.task.TIMER_LOG", log)
    return log


# ── _uid ──────────────────────────────────────────────────────────────────────

def test_uid_is_stable():
    """Same source ID must always produce the same UID.

    The UID is the only stable handle a user has for a task across sessions.
    Non-determinism here would break every lookup and log entry.
    """
    assert _uid("github:owner/repo#127") == _uid("github:owner/repo#127")


def test_uid_is_hex_only():
    """UIDs must be plain 8 hex chars with no prefix."""
    uid = _uid("github:owner/repo#1")
    assert len(uid) == 8
    assert all(c in "0123456789abcdef" for c in uid)


def test_uid_differs_across_tasks():
    """Different source IDs must produce different UIDs."""
    assert _uid("github:owner/repo#1") != _uid("github:owner/repo#2")


def test_uid_length():
    """UIDs must be exactly 8 hex characters."""
    assert len(_uid("github:owner/repo#1")) == 8


# ── _fmt_duration ─────────────────────────────────────────────────────────────

def test_fmt_duration_seconds():
    assert _fmt_duration(45) == "0m 45s"

def test_fmt_duration_minutes():
    assert _fmt_duration(125) == "2m 05s"

def test_fmt_duration_hours():
    assert _fmt_duration(3_661) == "1h 01m"


# ── event log ────────────────────────────────────────────────────────────────

def test_append_and_read_round_trip(isolated_timer_log):
    """Written events must be readable back with identical fields."""
    _append_event("start", "github:owner/repo#1", "Task A")
    events = _read_events()
    assert len(events) == 1
    assert events[0]["event"] == "start"
    assert events[0]["task_id"] == "github:owner/repo#1"


def test_active_period_detected(isolated_timer_log):
    """Unmatched start must be returned as the active period."""
    _append_event("start", "github:owner/repo#1", "Task A")
    assert _active_period() is not None


def test_active_period_cleared_after_stop(isolated_timer_log):
    """Matched start+stop must leave no active period."""
    _append_event("start", "github:owner/repo#1", "Task A")
    _append_event("stop",  "github:owner/repo#1", "Task A")
    assert _active_period() is None


# ── _totals_by_task_id ────────────────────────────────────────────────────────

def test_totals_accumulates_multiple_periods(isolated_timer_log, freezegun=None):
    """
    Two completed periods for the same task must be summed.

    report() and list() both depend on this accumulation being correct.
    A bug here would silently under-report time spent.
    """
    from datetime import datetime, timezone, timedelta
    import topgun.cli.task as task_mod

    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def make_event(event, task_id, title, offset_min):
        return {
            "event": event,
            "task_id": task_id,
            "task_title": title,
            "ts": (base + timedelta(minutes=offset_min)).isoformat(),
        }

    log = isolated_timer_log
    with log.open("w") as f:
        for rec in [
            make_event("start", "github:owner/repo#1", "T", 0),
            make_event("stop",  "github:owner/repo#1", "T", 30),
            make_event("start", "github:owner/repo#1", "T", 60),
            make_event("stop",  "github:owner/repo#1", "T", 90),
        ]:
            f.write(json.dumps(rec) + "\n")

    totals = _totals_by_task_id()
    assert totals["github:owner/repo#1"] == pytest.approx(3600.0)  # 2 × 30 min


# ── _intervals_by_task_id ─────────────────────────────────────────────────────

def test_intervals_returns_correct_count(isolated_timer_log):
    """
    Two completed periods must produce two interval entries.

    show() displays these rows — if count is wrong the output is misleading.
    """
    from datetime import datetime, timezone, timedelta

    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def ev(event, offset):
        return {"event": event, "task_id": "github:owner/repo#1",
                "task_title": "T", "ts": (base + timedelta(minutes=offset)).isoformat()}

    with isolated_timer_log.open("w") as f:
        for rec in [ev("start", 0), ev("stop", 15), ev("start", 30), ev("stop", 45)]:
            f.write(json.dumps(rec) + "\n")

    intervals = _intervals_by_task_id("github:owner/repo#1")
    assert len(intervals) == 2
    assert all(i["end"] is not None for i in intervals)


# ── _parse_filter ─────────────────────────────────────────────────────────────


def test_parse_filter_single_status():
    """status=closed must return ['closed'].

    _parse_filter drives the fetch_tasks statuses argument; wrong parsing
    means the wrong tasks are fetched.
    """
    assert _parse_filter("status=closed") == ["closed"]


def test_parse_filter_multiple_statuses():
    """Comma-separated statuses must all be returned."""
    result = _parse_filter("status=open,closed")
    assert set(result) == {"open", "closed"}


def test_parse_filter_defaults_to_open_on_empty():
    """An empty filter string must fall back to ['open']."""
    assert _parse_filter("") == ["open"]


def test_parse_filter_bare_value():
    """A bare status value (no key=) must be accepted."""
    assert _parse_filter("open") == ["open"]


# ── _slugify ──────────────────────────────────────────────────────────────────


def test_slugify_basic():
    """Spaces become hyphens and the result is lowercase.

    The slug is used as part of the vault directory name; a wrong slug
    would create an unreadable path or fail mkdir.
    """
    assert _slugify("Book Dentist Appointment") == "book-dentist-appointment"


def test_slugify_strips_punctuation():
    """Punctuation must be removed without leaving double-hyphens."""
    result = _slugify("Fix it! Now.")
    assert "!" not in result
    assert "--" not in result


def test_slugify_handles_unicode():
    """Non-ASCII characters must be transliterated or dropped, not raise."""
    result = _slugify("Café au lait")
    assert isinstance(result, str)
    assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in result)


# ── _write_obsidian_task ──────────────────────────────────────────────────────


def test_write_obsidian_task_creates_file(tmp_path):
    """write_obsidian_task must create a task.md inside a dated slug directory.

    This is the terminal action of `topgun task add`. If the file is not
    created, the task is silently lost.
    """
    structured = {
        "title": "Buy Groceries",
        "about": "Weekly restock.",
        "motivation": None,
        "acceptance_criteria": ["Groceries purchased"],
        "best_before": "2026-05-10",
        "must_before": None,
        "priority": "medium",
        "tags": ["personal"],
    }
    task_dir = _write_obsidian_task(str(tmp_path), structured)
    task_file = task_dir / "task.md"
    assert task_file.exists()
    content = task_file.read_text()
    assert "# Buy Groceries" in content
    assert "status: open" in content
    assert "2026-05-10" in content
    assert "- [ ] Groceries purchased" in content


def test_write_obsidian_task_slug_from_title(tmp_path):
    """The directory name must be based on a slugified version of the title."""
    structured = {
        "title": "Call The Bank",
        "about": "Monthly check.",
        "motivation": None,
        "acceptance_criteria": [],
        "best_before": None,
        "must_before": None,
        "priority": None,
        "tags": [],
    }
    task_dir = _write_obsidian_task(str(tmp_path), structured)
    assert "call-the-bank" in task_dir.name
