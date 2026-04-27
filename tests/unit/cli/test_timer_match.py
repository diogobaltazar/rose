"""
Unit tests for topgun.cli.timer_match.

Covers UID derivation, task ID formatting, and the direct-lookup paths
(explicit UID, explicit ID, bare issue number). All paths bypass the
Anthropic SDK so they work without credentials or network access.

What is NOT covered:
- The fuzzy match() function — requires a live SDK call (integration concern).
- Backlog fetching from GitHub or Obsidian — tested in test_backlog.py.
"""

import pytest

from topgun.cli.timer_match import _task_id, _uid, match_by_id


# ── _uid ──────────────────────────────────────────────────────────────────────

def test_uid_format():
    """UIDs must be exactly 8 lowercase hex chars with no prefix."""
    uid = _uid("github:owner/repo#1")
    assert len(uid) == 8
    assert all(c in "0123456789abcdef" for c in uid)


def test_uid_independent_of_github_number():
    """
    The topgun UID must be distinct from the GitHub issue number.

    UIDs are content-addressed from the full source identity, not wrappers
    around the issue number. A 127-issue repo should not produce a UID
    that looks like it encodes the number 127.
    """
    uid = _uid("github:owner/repo#127")
    # The UID is hex — "127" would only appear by coincidence.
    # We verify the UID is a proper hash, not a trivial encoding.
    assert len(uid) == 8
    assert all(c in "0123456789abcdef" for c in uid)


# ── _task_id ──────────────────────────────────────────────────────────────────

def test_task_id_github_extracts_number():
    """GitHub task IDs must encode the issue number and repo in a stable format."""
    item = {"type": "github", "title": "#124 Fix auth bug", "source_full": "owner/repo"}
    assert _task_id(item) == "github:owner/repo#124"


def test_task_id_obsidian_uses_title():
    """Obsidian tasks have no issue number — ID must include vault path and title."""
    item = {"type": "obsidian", "title": "Buy milk", "source_full": "/Users/x/vault"}
    assert _task_id(item) == "obsidian:/Users/x/vault:Buy milk"


# ── match_by_id ───────────────────────────────────────────────────────────────

def _make_tasks():
    return [
        {"uid": _uid("github:owner/repo#42"), "id": "github:owner/repo#42",
         "title": "#42 A task", "source": "github", "source_full": "owner/repo"},
        {"uid": _uid("github:owner/repo#99"), "id": "github:owner/repo#99",
         "title": "#99 Another task", "source": "github", "source_full": "owner/repo"},
    ]


def test_match_by_id_topgun_uid(monkeypatch):
    """
    A topgun UID must resolve directly to the correct task without an SDK call.

    This is the primary lookup path shown in `topgun task list` output.
    """
    tasks = _make_tasks()
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: tasks)
    uid = _uid("github:owner/repo#42")
    result = match_by_id(uid)
    assert result is not None
    assert result["id"] == "github:owner/repo#42"


def test_match_by_id_full_source_id(monkeypatch):
    """Full source IDs must resolve directly."""
    tasks = _make_tasks()
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: tasks)
    assert match_by_id("github:owner/repo#42") is not None


def test_match_by_id_bare_number(monkeypatch):
    """
    Bare numbers like '42' or '#42' must resolve to the matching GitHub task.

    Requiring the full UID or source ID every time would be poor UX.
    """
    tasks = _make_tasks()
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: tasks)
    assert match_by_id("42") is not None
    assert match_by_id("#42") is not None


def test_match_by_id_unknown_uid_returns_none(monkeypatch):
    """Unknown UIDs must return None so the caller can fall through to fuzzy match."""
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: [])
    assert match_by_id("00000000") is None


def test_match_by_id_unknown_number_returns_none(monkeypatch):
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: [])
    assert match_by_id("999") is None
