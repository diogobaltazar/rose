"""Unit tests for the timer service layer."""

import json

import pytest

from topgun.services.timer import (
    append_event,
    read_events,
    active_period,
    start_timer,
    stop_timer,
    timer_status,
    totals_by_task_id,
    intervals_by_task_id,
)


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    log = tmp_path / "timer.jsonl"
    monkeypatch.setattr("topgun.services.timer.TIMER_LOG", log)
    return log


def test_start_timer_writes_event(isolated_log):
    """start_timer must append a start event to the log."""
    record = start_timer("github:owner/repo#1", "Test task")
    assert record["event"] == "start"
    events = read_events()
    assert len(events) == 1


def test_stop_timer_returns_elapsed(isolated_log):
    """stop_timer must return elapsed time and task details."""
    start_timer("github:owner/repo#1", "Test task")
    result = stop_timer()
    assert result["task_id"] == "github:owner/repo#1"
    assert result["elapsed_s"] >= 0


def test_double_start_raises(isolated_log):
    """Starting a timer when one is running must raise ValueError."""
    start_timer("github:owner/repo#1", "Task A")
    with pytest.raises(ValueError, match="already running"):
        start_timer("github:owner/repo#2", "Task B")


def test_stop_without_start_raises(isolated_log):
    """Stopping when no timer is running must raise ValueError."""
    with pytest.raises(ValueError, match="No timer running"):
        stop_timer()


def test_timer_status_returns_none_when_idle(isolated_log):
    """timer_status must return None when no timer is running."""
    assert timer_status() is None


def test_timer_status_returns_active(isolated_log):
    """timer_status must return task details when a timer is running."""
    start_timer("github:owner/repo#1", "Active task")
    status = timer_status()
    assert status is not None
    assert status["task_id"] == "github:owner/repo#1"
    assert status["elapsed_s"] >= 0
