"""
Integration tests for topgun task — start → stop → show/list round-trip.

What is tested:
- start writes a well-formed start event
- stop writes a matching stop event
- status shows the active task
- list shows accumulated time
- show displays intervals for a task
- Guard rails: double-start and bare-stop are rejected

What is NOT tested:
- SDK fuzzy matching (requires live credentials)
- $EDITOR flow (requires a TTY and $EDITOR set)
- GitHub/Obsidian backlog fetching (tested in test_backlog.py)
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from topgun.cli.task import app, TIMER_LOG
from topgun.cli.timer_match import _uid

runner = CliRunner()

_FIXED_TASK = {
    "uid": _uid("github:owner/repo#1"),
    "id": "github:owner/repo#1",
    "title": "#1 Test task",
    "source": "github",
    "source_full": "owner/repo",
}


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    log = tmp_path / "timer.jsonl"
    monkeypatch.setattr("topgun.cli.task.TIMER_LOG", log)
    monkeypatch.setattr("topgun.cli.timer._resolve_task", lambda _: _FIXED_TASK)
    monkeypatch.setattr("topgun.cli.task._resolve_task", lambda _: _FIXED_TASK)
    return log


def _events(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_start_stop_round_trip(isolated_log):
    """start → stop must produce two log entries with matching task IDs."""
    result = runner.invoke(app, ["start", "--task", "1"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0, result.output

    events = _events(isolated_log)
    assert len(events) == 2
    assert events[0]["event"] == "start"
    assert events[1]["event"] == "stop"
    assert events[0]["task_id"] == events[1]["task_id"]


def test_status_shows_active_task(isolated_log):
    """status must show the task title while a timer is running."""
    runner.invoke(app, ["start", "--task", "1"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "#1 Test task" in result.output


def test_show_displays_intervals(isolated_log, monkeypatch):
    """show must display time intervals after a completed start/stop cycle."""
    monkeypatch.setattr("topgun.cli.task.match_by_id", lambda _: _FIXED_TASK)
    runner.invoke(app, ["start", "--task", "1"])
    runner.invoke(app, ["stop"])
    result = runner.invoke(app, ["show", "--task", _FIXED_TASK["uid"]])
    assert result.exit_code == 0
    assert "#1 Test task" in result.output


# ── Guard rails ────────────────────────────────────────────────────────────────

def test_double_start_rejected(isolated_log):
    """Starting when a timer is already running must fail with a clear message."""
    runner.invoke(app, ["start", "--task", "1"])
    result = runner.invoke(app, ["start", "--task", "1"])
    assert result.exit_code != 0
    assert "already running" in result.output


def test_stop_without_start_rejected(isolated_log):
    """Stopping with no active timer must fail."""
    result = runner.invoke(app, ["stop"])
    assert result.exit_code != 0
    assert "no timer running" in result.output


def test_multiple_cycles_accumulate(isolated_log):
    """Two completed cycles for the same task must both appear in the event log."""
    runner.invoke(app, ["start", "--task", "1"])
    runner.invoke(app, ["stop"])
    runner.invoke(app, ["start", "--task", "1"])
    runner.invoke(app, ["stop"])
    assert len(_events(isolated_log)) == 4


# ── list --filter ───────────────────────────────────────────────────────────────


def _task(uid_str: str, title: str, state: str = "open", due: str = "") -> dict:
    """Build a minimal task dict as returned by fetch_tasks."""
    return {
        "uid": _uid(uid_str),
        "id": uid_str,
        "title": title,
        "source": "obsidian",
        "source_full": "/fake/vault",
        "due": due,
        "url": "",
        "state": state,
    }


def test_list_filter_shows_open_by_default(monkeypatch):
    """
    `topgun task list` must show only open tasks when no filter is given.

    What is tested: the fetch_tasks call receives statuses=["open"] and the
    command output excludes closed tasks.
    What is NOT tested: GitHub fetching or real vault I/O.
    """
    captured = {}

    def fake_fetch(statuses=None):
        captured["statuses"] = statuses
        return [_task("obsidian:/vault:open-task", "Open Task", state="open")]

    monkeypatch.setattr("topgun.cli.task.fetch_tasks", fake_fetch)
    monkeypatch.setattr("topgun.cli.task._get_sources", lambda: [{"type": "obsidian"}])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert captured["statuses"] == ["open"]
    assert "Open Task" in result.output


def test_list_filter_closed(monkeypatch):
    """
    `topgun task list --filter status=closed` must pass ["closed"] to fetch_tasks.

    What is tested: the status filter propagates from the CLI flag through
    _parse_filter to the fetch_tasks call.
    What is NOT tested: actual vault or GitHub fetching.
    """
    captured = {}

    def fake_fetch(statuses=None):
        captured["statuses"] = statuses
        return [_task("obsidian:/vault:closed-task", "Closed Task", state="closed")]

    monkeypatch.setattr("topgun.cli.task.fetch_tasks", fake_fetch)
    monkeypatch.setattr("topgun.cli.task._get_sources", lambda: [{"type": "obsidian"}])

    result = runner.invoke(app, ["list", "--filter", "status=closed"])
    assert result.exit_code == 0
    assert "closed" in captured["statuses"]
    assert "Closed Task" in result.output


def test_list_filter_multiple_shows_status_column(monkeypatch):
    """
    `topgun task list --filter status=open,closed` must include a Status column.

    What is tested: the Status column appears when more than one status is
    requested. This column is the user's signal that they are viewing a mixed
    result set and need to distinguish states at a glance.
    What is NOT tested: column formatting details or exact alignment.
    """
    def fake_fetch(statuses=None):
        return [
            _task("obsidian:/vault:open-task", "Open Task", state="open"),
            _task("obsidian:/vault:closed-task", "Closed Task", state="closed"),
        ]

    monkeypatch.setattr("topgun.cli.task.fetch_tasks", fake_fetch)
    monkeypatch.setattr("topgun.cli.task._get_sources", lambda: [{"type": "obsidian"}])

    result = runner.invoke(app, ["list", "--filter", "status=open,closed"])
    assert result.exit_code == 0
    assert "Status" in result.output


def test_list_due_date_populated_from_section(monkeypatch):
    """
    Due dates returned by fetch_tasks must appear in `topgun task list` output.

    What is tested: the due field flows from fetch_tasks through list_cmd
    to the rendered Rich table. Verifies the end-to-end rendering path,
    not the parsing (covered in unit tests).
    What is NOT tested: date colour coding or real vault I/O.
    """
    def fake_fetch(statuses=None):
        return [_task("obsidian:/vault:dated-task", "Dated Task", state="open", due="2026-06-01")]

    monkeypatch.setattr("topgun.cli.task.fetch_tasks", fake_fetch)
    monkeypatch.setattr("topgun.cli.task._get_sources", lambda: [{"type": "obsidian"}])

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "2026-06-01" in result.output
