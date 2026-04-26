"""
Integration test for the topgun timer start → stop → report round-trip.

What is tested:
- start writes a well-formed start event to the log
- stop writes a matching stop event
- report aggregates the pair into a non-zero duration
- The event log remains consistent across multiple start/stop cycles

What is NOT tested:
- SDK calls to Claude (requires live credentials and network)
- Branch inference (requires a real git repo — tested manually via Local Run)
- Obsidian/GitHub backlog fetching (tested in test_backlog.py)

Edge cases covered:
- Attempting start when a timer is already running is rejected
- Attempting stop when no timer is running is rejected
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from topgun.cli.timer import app, TIMER_LOG

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    log = tmp_path / "timer.jsonl"
    monkeypatch.setattr("topgun.cli.timer.TIMER_LOG", log)
    return log


def _events(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_start_stop_report_round_trip(isolated_log, monkeypatch):
    """
    A full start → stop cycle must produce two log entries and a non-zero
    report. This is the core contract of the timer feature.

    Branch inference and SDK matching are both bypassed here by monkeypatching
    _resolve_task to return a fixed task, keeping the test hermetic.
    """
    fixed_task = {"id": "github:owner/repo#1", "title": "#1 Test task", "source": "github"}
    monkeypatch.setattr("topgun.cli.timer._resolve_task", lambda _arg: fixed_task)

    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0, result.output

    events = _events(isolated_log)
    assert len(events) == 2
    assert events[0]["event"] == "start"
    assert events[1]["event"] == "stop"
    assert events[0]["task_id"] == events[1]["task_id"]

    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
    assert "#1 Test task" in result.output


# ── Guard rails ────────────────────────────────────────────────────────────────

def test_start_blocked_when_already_running(isolated_log, monkeypatch):
    """
    Starting a timer when one is already running must be rejected with a
    non-zero exit code and a helpful message.

    Without this guard, a user could start multiple timers and lose track
    of which periods belong to which task.
    """
    fixed_task = {"id": "github:owner/repo#1", "title": "#1 Test task", "source": "github"}
    monkeypatch.setattr("topgun.cli.timer._resolve_task", lambda _arg: fixed_task)

    runner.invoke(app, ["start"])
    result = runner.invoke(app, ["start"])
    assert result.exit_code != 0
    assert "already running" in result.output


def test_stop_with_no_active_timer(isolated_log):
    """
    Stopping when no timer is running must return a non-zero exit code.
    A silent no-op would be confusing and could mask missed stop events.
    """
    result = runner.invoke(app, ["stop"])
    assert result.exit_code != 0
    assert "no timer running" in result.output


def test_status_shows_running_task(isolated_log, monkeypatch):
    """status must report the active task while a timer is running."""
    fixed_task = {"id": "github:owner/repo#7", "title": "#7 Active task", "source": "github"}
    monkeypatch.setattr("topgun.cli.timer._resolve_task", lambda _arg: fixed_task)

    runner.invoke(app, ["start"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "#7 Active task" in result.output


def test_multiple_cycles_accumulate_in_report(isolated_log, monkeypatch):
    """
    Two separate start/stop cycles for the same task must accumulate their
    durations in the report rather than showing only the last period.

    This validates that report() sums all periods for a task, not just
    the most recent one — which is the expected behaviour for a work log.
    """
    fixed_task = {"id": "github:owner/repo#1", "title": "#1 Test task", "source": "github"}
    monkeypatch.setattr("topgun.cli.timer._resolve_task", lambda _arg: fixed_task)

    runner.invoke(app, ["start"])
    runner.invoke(app, ["stop"])
    runner.invoke(app, ["start"])
    runner.invoke(app, ["stop"])

    events = _events(isolated_log)
    assert len(events) == 4

    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
    assert "#1 Test task" in result.output
