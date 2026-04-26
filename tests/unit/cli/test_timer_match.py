"""
Unit tests for topgun.cli.timer_match.

Covers task ID derivation and the two direct-lookup paths (branch inference
and explicit ID). These paths deliberately bypass the Anthropic SDK so they
must work correctly without any API credentials or network access.

What is NOT covered here:
- The fuzzy match() function — it requires a live SDK call and is an
  integration concern tested separately.
- Backlog fetching from GitHub or Obsidian — tested in test_backlog.py.
"""

import pytest

from topgun.cli.timer_match import _task_id, match_by_branch, match_by_id


# ── _task_id ──────────────────────────────────────────────────────────────────

def test_task_id_github_extracts_number():
    """
    GitHub task IDs must encode the issue number and repo in a stable format.

    Consumers (timer report, event log lookup) key on this string. A change
    in format would silently break aggregation across start/stop pairs that
    were written with the old format.
    """
    item = {"type": "github", "title": "#124 Fix auth bug", "source_full": "owner/repo"}
    assert _task_id(item) == "github:owner/repo#124"


def test_task_id_obsidian_uses_title():
    """Obsidian tasks have no issue number — ID must include vault path and title."""
    item = {"type": "obsidian", "title": "Buy milk", "source_full": "/Users/x/vault"}
    assert _task_id(item) == "obsidian:/Users/x/vault:Buy milk"


# ── match_by_branch ───────────────────────────────────────────────────────────

def test_match_by_branch_extracts_github_issue(monkeypatch):
    """
    Branch names like feat/124-short-desc must resolve to the matching GitHub task.

    This is the zero-argument fast path: the user runs `topgun timer start`
    from a feature branch and the task is inferred without any user input or
    API call. If the extraction regex is wrong, every branch-based start fails.
    """
    tasks = [
        {"id": "github:owner/repo#124", "title": "#124 Fix auth", "source": "github"},
        {"id": "github:owner/repo#125", "title": "#125 Add logging", "source": "github"},
    ]
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: tasks)

    result = match_by_branch("feat/124-fix-auth-bug")
    assert result is not None
    assert result["id"] == "github:owner/repo#124"


def test_match_by_branch_no_match_returns_none(monkeypatch):
    """Branches without an issue number (e.g. 'main', 'hotfix-typo') must return None."""
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: [])
    assert match_by_branch("main") is None
    assert match_by_branch("hotfix-typo") is None


def test_match_by_branch_number_not_in_backlog(monkeypatch):
    """A valid branch pattern whose issue is not in the backlog must return None."""
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: [])
    assert match_by_branch("feat/999-nonexistent") is None


# ── match_by_id ───────────────────────────────────────────────────────────────

def test_match_by_id_exact_full_id(monkeypatch):
    """Full IDs must resolve directly without Claude."""
    tasks = [{"id": "github:owner/repo#42", "title": "#42 A task", "source": "github"}]
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: tasks)
    result = match_by_id("github:owner/repo#42")
    assert result is not None
    assert result["id"] == "github:owner/repo#42"


def test_match_by_id_bare_number(monkeypatch):
    """
    Bare numbers like "42" or "#42" must resolve to the matching GitHub task.

    This covers the common case where a user runs `topgun timer start --task 42`.
    Requiring the full ID string would be poor UX.
    """
    tasks = [{"id": "github:owner/repo#42", "title": "#42 A task", "source": "github"}]
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: tasks)

    assert match_by_id("42") is not None
    assert match_by_id("#42") is not None


def test_match_by_id_not_found_returns_none(monkeypatch):
    """Unknown IDs must return None so the caller can fall through to fuzzy match."""
    monkeypatch.setattr("topgun.cli.timer_match.fetch_tasks", lambda: [])
    assert match_by_id("999") is None
