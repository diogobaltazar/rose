"""
Unit tests for the calendar scheduling algorithm.

Tests the slot-finding and task-scheduling logic independently of
the CalDAV network layer.
"""

import datetime

import pytest

from topgun.services.calendar import CalendarService, TimeSlot


@pytest.fixture
def svc(monkeypatch):
    """CalendarService with no network dependency."""
    monkeypatch.setenv("TOPGUN_CONFIG", "/nonexistent")
    s = CalendarService.__new__(CalendarService)
    s.username = ""
    s.password = ""
    s.calendar_name = "Test"
    s.avail_start = datetime.time(20, 0)
    s.avail_end = datetime.time(5, 0)
    s.buffer_minutes = 30
    s.default_duration = 60
    s._client = None
    s._principal = None
    s._calendar = None
    return s


class TestAvailableWindows:
    def test_overnight_window_generated(self, svc):
        """20:00-05:00 should produce one 9-hour window per night."""
        start = datetime.datetime(2026, 5, 3, 18, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 5, 4, 10, 0, tzinfo=datetime.timezone.utc)
        windows = svc._generate_available_windows(start, end)
        assert len(windows) >= 1
        w = windows[0]
        assert w.start.hour == 20
        assert w.end.hour == 5

    def test_window_respects_after(self, svc):
        """If 'after' is 22:00, the window should start at 22:00 not 20:00."""
        start = datetime.datetime(2026, 5, 3, 22, 0, tzinfo=datetime.timezone.utc)
        end = datetime.datetime(2026, 5, 4, 10, 0, tzinfo=datetime.timezone.utc)
        windows = svc._generate_available_windows(start, end)
        assert windows[0].start.hour == 22


class TestFindAvailableSlots:
    def test_finds_slot_when_empty(self, svc, monkeypatch):
        """With no existing events, should find a slot immediately."""
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: [])
        after = datetime.datetime(2026, 5, 3, 20, 0, tzinfo=datetime.timezone.utc)
        slots = svc.find_available_slots(60, after=after)
        assert len(slots) >= 1
        assert slots[0].start == after
        assert (slots[0].end - slots[0].start) == datetime.timedelta(hours=1)

    def test_respects_existing_event(self, svc, monkeypatch):
        """Slot should start after existing event + buffer."""
        existing = [TimeSlot(
            start=datetime.datetime(2026, 5, 3, 20, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2026, 5, 3, 21, 0, tzinfo=datetime.timezone.utc),
        )]
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: existing)
        after = datetime.datetime(2026, 5, 3, 20, 0, tzinfo=datetime.timezone.utc)
        slots = svc.find_available_slots(60, after=after)
        assert len(slots) >= 1
        assert slots[0].start >= datetime.datetime(2026, 5, 3, 21, 30, tzinfo=datetime.timezone.utc)

    def test_no_slot_if_window_full(self, svc, monkeypatch):
        """If the entire window is blocked, returns empty."""
        existing = [TimeSlot(
            start=datetime.datetime(2026, 5, 3, 19, 30, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2026, 5, 4, 5, 30, tzinfo=datetime.timezone.utc),
        )]
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: existing)
        after = datetime.datetime(2026, 5, 3, 20, 0, tzinfo=datetime.timezone.utc)
        until = datetime.datetime(2026, 5, 4, 5, 0, tzinfo=datetime.timezone.utc)
        slots = svc.find_available_slots(60, after=after, until=until)
        assert len(slots) == 0


class TestScheduleTasks:
    def test_schedules_single_task(self, svc, monkeypatch):
        """A single task should be placed in the first available slot."""
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: [])
        monkeypatch.setattr("topgun.services.calendar_state.get_event_mapping", lambda tid: None)

        tasks = [{"id": "test:1", "title": "Study", "state": "open",
                  "due": "2026-05-10", "priority": "medium", "estimated_minutes": 90}]
        result = svc.schedule_tasks(tasks)
        assert len(result.scheduled) >= 1
        assert result.scheduled[0].task_id == "test:1"

    def test_respects_priority_ordering(self, svc, monkeypatch):
        """High-priority task with same deadline should be scheduled first."""
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: [])
        monkeypatch.setattr("topgun.services.calendar_state.get_event_mapping", lambda tid: None)

        tasks = [
            {"id": "test:low", "title": "Low", "state": "open",
             "due": "2026-05-10", "priority": "low", "estimated_minutes": 60},
            {"id": "test:high", "title": "High", "state": "open",
             "due": "2026-05-10", "priority": "high", "estimated_minutes": 60},
        ]
        result = svc.schedule_tasks(tasks)
        assert result.scheduled[0].task_id == "test:high"

    def test_skips_user_modified(self, svc, monkeypatch):
        """Tasks whose calendar events were user-modified should not be rescheduled."""
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: [])
        monkeypatch.setattr(
            "topgun.services.calendar_state.get_event_mapping",
            lambda tid: {"user_modified": True} if tid == "test:1" else None,
        )

        tasks = [{"id": "test:1", "title": "Modified", "state": "open",
                  "due": "2026-05-10", "priority": "medium", "estimated_minutes": 60}]
        result = svc.schedule_tasks(tasks)
        assert len(result.scheduled) == 0

    def test_closed_tasks_skipped(self, svc, monkeypatch):
        """Closed tasks are not scheduled."""
        monkeypatch.setattr(svc, "get_existing_events", lambda s, e: [])
        monkeypatch.setattr("topgun.services.calendar_state.get_event_mapping", lambda tid: None)

        tasks = [{"id": "test:1", "title": "Done", "state": "closed",
                  "due": "2026-05-10", "priority": "medium", "estimated_minutes": 60}]
        result = svc.schedule_tasks(tasks)
        assert len(result.scheduled) == 0
