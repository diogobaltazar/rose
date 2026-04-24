"""
Unit tests for topgun.cli.backlog.

Covers the parsing helpers that convert raw GitHub issues and Obsidian
markdown lines into the unified backlog item shape. These are the most
critical units: if parsing is wrong, every consumer (terminal watch,
web UI, /topgun-backlog command) sees wrong data.

Integration tests (live gh CLI, real vault) are out of scope here.
"""

import textwrap

import pytest

from topgun.cli.backlog import (
    _parse_body_section,
    _is_overdue,
)


# ── _parse_body_section ───────────────────────────────────────────────────────


def test_parse_body_section_extracts_text():
    """Section parser must return the trimmed text under the requested heading.

    This validates the core GitHub issue body parser. If it fails, all
    structured fields (must_before, best_before, about, etc.) return None
    for every GitHub issue.
    """
    body = textwrap.dedent("""\
        ## About
        A task about something important.

        ## Motivation
        Because it matters.

        ## Best Before
        2026-05-01
    """)
    assert _parse_body_section(body, "About") == "A task about something important."
    assert _parse_body_section(body, "Motivation") == "Because it matters."
    assert _parse_body_section(body, "Best Before") == "2026-05-01"


def test_parse_body_section_missing_returns_empty():
    """Absent sections must return an empty string, not raise.

    Callers use `or None` to convert empty → None; an exception here
    would crash the entire GitHub fetch for the affected repo.
    """
    body = "## About\nSomething.\n"
    assert _parse_body_section(body, "Must Before") == ""


def test_parse_body_section_empty_body():
    """Empty or None body must never raise."""
    assert _parse_body_section("", "About") == ""
    assert _parse_body_section(None, "About") == ""  # type: ignore[arg-type]


# ── _is_overdue ───────────────────────────────────────────────────────────────


def test_is_overdue_past_must_before():
    """An open item with must_before in the past is overdue.

    This drives both the web UI highlight and the terminal bold styling.
    Wrong results here silently misprioritise the backlog.
    """
    item = {"state": "open", "must_before": "2000-01-01", "best_before": None}
    assert _is_overdue(item) is True


def test_is_overdue_future_must_before():
    """An open item with must_before in the future is not overdue."""
    item = {"state": "open", "must_before": "2099-12-31", "best_before": None}
    assert _is_overdue(item) is False


def test_is_overdue_closed_item_never_overdue():
    """Closed items are never overdue regardless of dates.

    Ensures that historical closed items with past due dates do not appear
    as overdue in the gamification panel's overdue count.
    """
    item = {"state": "closed", "must_before": "2000-01-01", "best_before": None}
    assert _is_overdue(item) is False


def test_is_overdue_falls_back_to_best_before():
    """When must_before is absent, overdue is assessed against best_before."""
    item = {"state": "open", "must_before": None, "best_before": "2000-01-01"}
    assert _is_overdue(item) is True


def test_is_overdue_no_dates():
    """Items with no dates are never overdue."""
    item = {"state": "open", "must_before": None, "best_before": None}
    assert _is_overdue(item) is False
