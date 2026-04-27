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
    _parse_frontmatter,
    _fetch_obsidian,
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


# ── _parse_frontmatter ────────────────────────────────────────────────────────


def test_parse_frontmatter_extracts_scalar_fields():
    """Frontmatter parser must return key-value pairs from the YAML block.

    This is the source of the status and priority fields for Obsidian tasks.
    If it breaks, status filtering and priority display both fail silently.
    """
    text = "---\ndate: 2026-04-26\nstatus: open\npriority: high\n---\n\n# Title\n"
    fm = _parse_frontmatter(text)
    assert fm["status"] == "open"
    assert fm["priority"] == "high"
    assert fm["date"] == "2026-04-26"


def test_parse_frontmatter_handles_quoted_values():
    """Quoted string values must be stripped of their quotes."""
    text = '---\ntags: ["health"]\nstatus: "closed"\n---\n'
    fm = _parse_frontmatter(text)
    assert fm["status"] == "closed"


def test_parse_frontmatter_missing_returns_empty():
    """Files without frontmatter must return an empty dict, not raise."""
    text = "# No frontmatter here\n\nJust content.\n"
    assert _parse_frontmatter(text) == {}


# ── _fetch_obsidian due date fix ──────────────────────────────────────────────


def _make_task_file(tmp_path, slug: str, status: str = "open", best_before: str = "_none_", must_before: str = "_none_") -> None:
    """Write a minimal directory-based task.md to a temp vault."""
    task_dir = tmp_path / slug
    task_dir.mkdir()
    content = (
        f"---\ndate: 2026-04-26\ntags: []\nstatus: {status}\npriority: \n---\n\n"
        f"# {slug}\n\n## About\n\n_none_\n\n## Motivation\n\n_none_\n\n"
        f"## Acceptance Criteria\n\n- [ ] Do the thing\n\n"
        f"## Best Before\n\n{best_before}\n\n## Must Before\n\n{must_before}\n"
    )
    (task_dir / "task.md").write_text(content, encoding="utf-8")


def test_fetch_obsidian_due_date_from_best_before(tmp_path):
    """Due date must be populated from the Best Before section for task.md files.

    This is the core fix: previously _fetch_obsidian only looked for emoji
    patterns on checkbox lines. Directory-based tasks use section headings.
    """
    _make_task_file(tmp_path, "my-task", best_before="2026-05-15")
    items = _fetch_obsidian(str(tmp_path))
    assert len(items) == 1
    assert items[0]["due"] == "2026-05-15"


def test_fetch_obsidian_due_date_must_before_takes_priority(tmp_path):
    """Must Before must take priority over Best Before when both are set."""
    _make_task_file(tmp_path, "urgent-task", best_before="2026-05-15", must_before="2026-05-01")
    items = _fetch_obsidian(str(tmp_path))
    assert len(items) == 1
    assert items[0]["due"] == "2026-05-01"


def test_fetch_obsidian_none_due_date_shows_empty(tmp_path):
    """A _none_ Best Before must produce an empty due string, not '_none_'."""
    _make_task_file(tmp_path, "no-date-task", best_before="_none_")
    items = _fetch_obsidian(str(tmp_path))
    assert len(items) == 1
    assert items[0]["due"] == ""


def test_fetch_obsidian_status_filter_open_only(tmp_path):
    """Default status filter (open) must exclude closed tasks.

    This ensures topgun task list (default) does not show completed work.
    """
    _make_task_file(tmp_path, "open-task", status="open")
    _make_task_file(tmp_path, "closed-task", status="closed")
    items = _fetch_obsidian(str(tmp_path), statuses=["open"])
    titles = [i["title"] for i in items]
    assert any("open-task" in t or "Do the thing" in t for t in titles)
    assert len(items) == 1


def test_fetch_obsidian_status_filter_closed(tmp_path):
    """Requesting status=closed must return only closed tasks."""
    _make_task_file(tmp_path, "open-task", status="open")
    _make_task_file(tmp_path, "closed-task", status="closed")
    items = _fetch_obsidian(str(tmp_path), statuses=["closed"])
    assert len(items) == 1
    assert items[0]["state"] == "closed"


def test_fetch_obsidian_status_filter_multiple(tmp_path):
    """Requesting status=open,closed must return both."""
    _make_task_file(tmp_path, "open-task", status="open")
    _make_task_file(tmp_path, "closed-task", status="closed")
    items = _fetch_obsidian(str(tmp_path), statuses=["open", "closed"])
    assert len(items) == 2
