"""
Calendar service — CalDAV integration with iCloud and task scheduling algorithm.

Connects to Apple Calendar via CalDAV, schedules tasks as VEVENT entries
using an earliest-available-slot algorithm, and supports bidirectional
sync with user edit detection.
"""

from __future__ import annotations

import datetime
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import caldav
from icalendar import Calendar as iCalendar, Event as iEvent

from topgun.services import calendar_state as state

DEFAULT_CALENDAR_NAME = "Topgun"
DEFAULT_AVAILABLE_START = datetime.time(20, 0)
DEFAULT_AVAILABLE_END = datetime.time(5, 0)
DEFAULT_BUFFER_MINUTES = 30
DEFAULT_DURATION_MINUTES = 60

CONFIG_FILE = Path(os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config" / "topgun" / "config.json")))


@dataclass
class TimeSlot:
    start: datetime.datetime
    end: datetime.datetime
    task_id: str | None = None
    task_title: str | None = None


@dataclass
class ScheduleResult:
    scheduled: list[TimeSlot] = field(default_factory=list)
    unschedulable: list[dict] = field(default_factory=list)


@dataclass
class SyncResult:
    new_token: str | None = None
    user_modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0


def _read_calendar_config() -> dict:
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        return cfg.get("calendar", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _parse_time(s: str) -> datetime.time:
    parts = s.split(":")
    return datetime.time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


class CalendarService:
    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        calendar_name: str | None = None,
    ):
        cfg = _read_calendar_config()
        self.username = username or cfg.get("username", "")
        self.password = password or cfg.get("password", "")
        self.calendar_name = calendar_name or cfg.get("calendar_name", DEFAULT_CALENDAR_NAME)

        avail = cfg.get("available_hours", {})
        self.avail_start = _parse_time(avail.get("start", "20:00"))
        self.avail_end = _parse_time(avail.get("end", "05:00"))
        self.buffer_minutes = cfg.get("buffer_minutes", DEFAULT_BUFFER_MINUTES)
        self.default_duration = cfg.get("default_duration_minutes", DEFAULT_DURATION_MINUTES)

        self._client: caldav.DAVClient | None = None
        self._principal: Any = None
        self._calendar: caldav.Calendar | None = None

    def connect(self) -> bool:
        if not self.username or not self.password:
            return False
        try:
            self._client = caldav.DAVClient(
                url="https://caldav.icloud.com/",
                username=self.username,
                password=self.password,
            )
            self._principal = self._client.principal()
            return True
        except Exception:
            return False

    def get_or_create_calendar(self) -> caldav.Calendar | None:
        if not self._principal:
            return None
        for cal in self._principal.calendars():
            if cal.name == self.calendar_name:
                self._calendar = cal
                state.set_calendar_url(str(cal.url))
                return cal
        try:
            cal = self._principal.make_calendar(name=self.calendar_name)
            self._calendar = cal
            state.set_calendar_url(str(cal.url))
            return cal
        except Exception:
            return None

    def get_existing_events(
        self, start: datetime.datetime, end: datetime.datetime
    ) -> list[TimeSlot]:
        if not self._calendar:
            return []
        try:
            events = self._calendar.search(
                start=start, end=end, event=True, expand=True
            )
        except Exception:
            return []

        slots = []
        for ev in events:
            try:
                comp = ev.icalendar_component
                dtstart = comp.get("DTSTART").dt
                dtend = comp.get("DTEND").dt
                if isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
                    dtstart = datetime.datetime.combine(dtstart, datetime.time.min, tzinfo=datetime.timezone.utc)
                    dtend = datetime.datetime.combine(dtend, datetime.time.min, tzinfo=datetime.timezone.utc)
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=datetime.timezone.utc)
                if dtend.tzinfo is None:
                    dtend = dtend.replace(tzinfo=datetime.timezone.utc)
                slots.append(TimeSlot(start=dtstart, end=dtend))
            except Exception:
                continue
        return slots

    def _generate_available_windows(
        self, after: datetime.datetime, until: datetime.datetime
    ) -> list[TimeSlot]:
        """Generate available time windows within the configured hours."""
        windows = []
        current = after.replace(hour=0, minute=0, second=0, microsecond=0)

        while current < until:
            if self.avail_start > self.avail_end:
                # Overnight window (e.g., 20:00-05:00)
                win_start = current.replace(
                    hour=self.avail_start.hour, minute=self.avail_start.minute
                )
                win_end = (current + datetime.timedelta(days=1)).replace(
                    hour=self.avail_end.hour, minute=self.avail_end.minute
                )
            else:
                win_start = current.replace(
                    hour=self.avail_start.hour, minute=self.avail_start.minute
                )
                win_end = current.replace(
                    hour=self.avail_end.hour, minute=self.avail_end.minute
                )

            if win_start < after:
                win_start = after
            if win_end > until:
                win_end = until
            if win_start < win_end:
                windows.append(TimeSlot(start=win_start, end=win_end))

            current += datetime.timedelta(days=1)

        return windows

    def find_available_slots(
        self,
        duration_minutes: int,
        after: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
        max_slots: int = 10,
    ) -> list[TimeSlot]:
        """Find available time slots of the given duration."""
        now = datetime.datetime.now(datetime.timezone.utc)
        if after is None:
            after = now
        if until is None:
            until = after + datetime.timedelta(days=30)

        existing = self.get_existing_events(after, until)
        buffer = datetime.timedelta(minutes=self.buffer_minutes)
        duration = datetime.timedelta(minutes=duration_minutes)

        blocked = []
        for ev in existing:
            blocked.append(TimeSlot(
                start=ev.start - buffer,
                end=ev.end + buffer,
            ))
        blocked.sort(key=lambda s: s.start)

        windows = self._generate_available_windows(after, until)
        result = []

        for window in windows:
            cursor = window.start
            for block in blocked:
                if block.end <= cursor:
                    continue
                if block.start >= window.end:
                    break
                if block.start > cursor and (block.start - cursor) >= duration:
                    result.append(TimeSlot(start=cursor, end=cursor + duration))
                    if len(result) >= max_slots:
                        return result
                cursor = max(cursor, block.end)

            if cursor + duration <= window.end:
                result.append(TimeSlot(start=cursor, end=cursor + duration))
                if len(result) >= max_slots:
                    return result

        return result

    def schedule_tasks(self, tasks: list[dict]) -> ScheduleResult:
        """Schedule tasks using earliest-available-slot algorithm."""
        result = ScheduleResult()
        now = datetime.datetime.now(datetime.timezone.utc)

        schedulable = []
        for t in tasks:
            if t.get("state") != "open":
                continue
            mapping = state.get_event_mapping(t.get("id", ""))
            if mapping and mapping.get("user_modified"):
                continue
            due = t.get("due") or t.get("must_before") or t.get("best_before")
            estimated = t.get("estimated_minutes", self.default_duration)
            schedulable.append({**t, "_due": due, "_estimated": estimated})

        schedulable.sort(key=lambda t: (t["_due"] or "9999-99-99", {"high": 0, "medium": 1, "low": 2}.get(t.get("priority", ""), 3)))

        until = now + datetime.timedelta(days=60)
        existing = self.get_existing_events(now, until)
        buffer = datetime.timedelta(minutes=self.buffer_minutes)

        blocked: list[TimeSlot] = []
        for ev in existing:
            blocked.append(TimeSlot(start=ev.start - buffer, end=ev.end + buffer))

        for task in schedulable:
            duration = datetime.timedelta(minutes=task["_estimated"])
            deadline = None
            if task["_due"]:
                try:
                    deadline = datetime.datetime.fromisoformat(task["_due"]).replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    try:
                        deadline = datetime.datetime.combine(
                            datetime.date.fromisoformat(task["_due"]),
                            datetime.time(23, 59),
                            tzinfo=datetime.timezone.utc,
                        )
                    except ValueError:
                        pass

            search_until = deadline or until
            windows = self._generate_available_windows(now, search_until)
            placed = False

            remaining = duration
            sessions = []

            for window in windows:
                if remaining <= datetime.timedelta(0):
                    break

                cursor = window.start
                blocked_sorted = sorted(blocked, key=lambda s: s.start)

                for block in blocked_sorted:
                    if block.end <= cursor:
                        continue
                    if block.start >= window.end:
                        break
                    available = block.start - cursor
                    if available > datetime.timedelta(minutes=15):
                        chunk = min(available, remaining)
                        sessions.append(TimeSlot(
                            start=cursor, end=cursor + chunk,
                            task_id=task.get("id"), task_title=task.get("title"),
                        ))
                        remaining -= chunk
                        if remaining <= datetime.timedelta(0):
                            break
                    cursor = max(cursor, block.end)

                if remaining > datetime.timedelta(0) and cursor < window.end:
                    available = window.end - cursor
                    chunk = min(available, remaining)
                    if chunk > datetime.timedelta(minutes=15):
                        sessions.append(TimeSlot(
                            start=cursor, end=cursor + chunk,
                            task_id=task.get("id"), task_title=task.get("title"),
                        ))
                        remaining -= chunk

            if remaining <= datetime.timedelta(0):
                for slot in sessions:
                    blocked.append(TimeSlot(start=slot.start - buffer, end=slot.end + buffer))
                    result.scheduled.append(slot)
            else:
                result.unschedulable.append({
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "reason": "No available slot before deadline",
                })

        return result

    def create_event(self, slot: TimeSlot) -> str | None:
        """Push a VEVENT to the calendar. Returns the event URL."""
        if not self._calendar:
            return None

        event_uid = str(uuid.uuid4()).upper()
        now = datetime.datetime.now(datetime.timezone.utc)

        dtstart = slot.start.strftime("%Y%m%dT%H%M%SZ")
        dtend = slot.end.strftime("%Y%m%dT%H%M%SZ")
        dtstamp = now.strftime("%Y%m%dT%H%M%SZ")

        payload = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Topgun//CalDAV//EN
BEGIN:VEVENT
UID:{event_uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{slot.task_title or 'Task'}
DESCRIPTION:Scheduled by Topgun
END:VEVENT
END:VCALENDAR"""

        try:
            ev = self._calendar.add_event(payload)
            event_url = str(ev.url)
            state.set_event_mapping(
                task_id=slot.task_id or event_uid,
                event_url=event_url,
                event_uid=event_uid,
                scheduled_start=slot.start.isoformat(),
                scheduled_end=slot.end.isoformat(),
            )
            return event_url
        except Exception:
            return None

    def delete_event(self, event_url: str) -> bool:
        if not self._client:
            return False
        try:
            ev = caldav.Event(client=self._client, url=event_url)
            ev.delete()
            return True
        except Exception:
            return False

    def sync(self) -> SyncResult:
        """Delta sync using RFC 6578 sync tokens."""
        result = SyncResult()
        if not self._calendar:
            return result

        token = state.get_sync_token()
        mappings = state.get_all_event_mappings()
        url_to_task = {m["event_url"]: tid for tid, m in mappings.items()}

        try:
            objects = self._calendar.objects_by_sync_token(sync_token=token, load_objects=True)
        except Exception:
            try:
                objects = self._calendar.objects_by_sync_token(load_objects=True)
            except Exception:
                return result

        for obj in objects:
            url_str = str(obj.url)
            if url_str not in url_to_task:
                result.unchanged += 1
                continue

            task_id = url_to_task[url_str]
            mapping = mappings.get(task_id)
            if not mapping:
                continue

            if not obj.data:
                state.remove_event_mapping(task_id)
                result.deleted.append(task_id)
                continue

            try:
                comp = obj.icalendar_component
                dtstart = comp.get("DTSTART").dt
                if isinstance(dtstart, datetime.date) and not isinstance(dtstart, datetime.datetime):
                    dtstart = datetime.datetime.combine(dtstart, datetime.time.min, tzinfo=datetime.timezone.utc)
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=datetime.timezone.utc)

                original_start = mapping.get("scheduled_start", "")
                if original_start and dtstart.isoformat() != original_start:
                    state.mark_user_modified(task_id)
                    result.user_modified.append(task_id)
                else:
                    result.unchanged += 1
            except Exception:
                result.unchanged += 1

        try:
            new_token = objects.sync_token
            if new_token:
                state.set_sync_token(new_token)
                result.new_token = new_token
        except (AttributeError, Exception):
            pass

        return result

    def schedule_and_push(self, tasks: list[dict]) -> ScheduleResult:
        """Schedule tasks and push events to the calendar."""
        schedule = self.schedule_tasks(tasks)
        for slot in schedule.scheduled:
            self.create_event(slot)
        return schedule

    def get_status(self) -> dict:
        full_state = state.get_full_state()
        return {
            "connected": self._client is not None,
            "calendar_name": self.calendar_name,
            "calendar_url": full_state.get("calendar_url"),
            "sync_token": full_state.get("sync_token"),
            "scheduled_events": len(full_state.get("events", {})),
            "events": full_state.get("events", {}),
        }
