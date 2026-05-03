"""Unit tests for the task service layer."""

import pytest

from topgun.services.tasks import _sort_items, _normalize_items


def _task(title, priority="", due="", state="open", source="github"):
    return {
        "uid": "aaaaaaaa",
        "id": f"{source}:owner/repo#1",
        "title": title,
        "source": source,
        "source_full": "owner/repo",
        "priority": priority,
        "due": due,
        "scheduled": "",
        "state": state,
        "created_at": "",
        "url": "",
    }


def test_sort_by_priority():
    """High priority tasks must sort before medium and low."""
    items = [
        _task("Low", priority="low"),
        _task("High", priority="high"),
        _task("Medium", priority="medium"),
    ]
    sorted_items = _sort_items(items, "priority", "asc")
    assert sorted_items[0]["title"] == "High"
    assert sorted_items[1]["title"] == "Medium"
    assert sorted_items[2]["title"] == "Low"


def test_sort_by_title():
    """Tasks must sort alphabetically by title."""
    items = [_task("Zebra"), _task("Alpha"), _task("Middle")]
    sorted_items = _sort_items(items, "title", "asc")
    assert sorted_items[0]["title"] == "Alpha"
    assert sorted_items[2]["title"] == "Zebra"


def test_sort_desc():
    """Descending order must reverse the sort."""
    items = [_task("Alpha"), _task("Zebra")]
    sorted_items = _sort_items(items, "title", "desc")
    assert sorted_items[0]["title"] == "Zebra"


def test_sort_by_due():
    """Tasks with earlier due dates must sort first."""
    items = [
        _task("Later", due="2026-12-01"),
        _task("Soon", due="2026-01-01"),
        _task("No due"),
    ]
    sorted_items = _sort_items(items, "due", "asc")
    assert sorted_items[0]["title"] == "Soon"
    assert sorted_items[1]["title"] == "Later"
    assert sorted_items[2]["title"] == "No due"


def test_sort_by_state():
    """Closed tasks must sort after open ones."""
    items = [
        _task("Closed", state="closed"),
        _task("Open", state="open"),
    ]
    sorted_items = _sort_items(items, "state", "asc")
    assert sorted_items[0]["title"] == "Closed"
    assert sorted_items[1]["title"] == "Open"
