"""
Task matching for topgun timer.

Fetches open tasks from all configured backlog sources and uses Claude Haiku
to fuzzy-match a natural language query against them, returning ranked candidates.
"""

import json
import re

from topgun.cli.backlog import _fetch_all, _get_sources
from topgun.inference.anthropic import call, load_prompt

_BRANCH_RE = re.compile(r"(?:feat|fix|chore|refactor|docs)/(\d+)-")
_GITHUB_NUM_RE = re.compile(r"^#?(\d+)$")


def _task_id(item: dict) -> str:
    """Derive a stable string ID from a backlog item."""
    if item["type"] == "github":
        # title is formatted as "#124 Some Title" by the backlog fetcher
        m = re.match(r"^#(\d+)\s", item["title"])
        number = m.group(1) if m else "?"
        return f"github:{item['source_full']}#{number}"
    # Obsidian tasks have no canonical ID — use source path + title
    return f"obsidian:{item['source_full']}:{item['title']}"


def fetch_tasks() -> list[dict]:
    """Return all open backlog tasks as {id, title, source} dicts."""
    sources = _get_sources()
    if not sources:
        return []
    items, _ = _fetch_all(sources)
    return [
        {"id": _task_id(item), "title": item["title"], "source": item["type"]}
        for item in items
    ]


def match(query: str) -> list[dict]:
    """
    Return ranked task candidates matching the natural language query.

    Returns a list of dicts: [{id, title, source, score}, ...], at most 5.
    Returns an empty list if no tasks are configured or nothing matches.
    """
    tasks = fetch_tasks()
    if not tasks:
        return []

    # Build user message: task list + query
    task_lines = "\n".join(
        f'{t["id"]} | {t["source"]} | {t["title"]}' for t in tasks
    )
    user_message = f"Tasks:\n{task_lines}\n\nQuery: {query}"

    system = load_prompt("timer_match")
    raw = call(prompt=user_message, system=system, command="timer")

    try:
        candidates = json.loads(raw)
        if not isinstance(candidates, list):
            return []
        return candidates
    except json.JSONDecodeError:
        return []


def match_by_branch(branch: str) -> dict | None:
    """
    Infer the task from a git branch name.

    Extracts an issue number from branch names like feat/124-short-description
    and looks it up directly in the task list — no SDK call needed.
    """
    m = _BRANCH_RE.search(branch)
    if not m:
        return None
    number = m.group(1)
    tasks = fetch_tasks()
    for task in tasks:
        if task["id"].endswith(f"#{number}"):
            return task
    return None


def match_by_id(task_id: str) -> dict | None:
    """
    Look up a task by explicit ID or bare issue number — no SDK call.

    Accepts: "124", "#124", or a full ID like "github:owner/repo#124".
    """
    tasks = fetch_tasks()

    # Full ID match
    for task in tasks:
        if task["id"] == task_id:
            return task

    # Bare number match against GitHub tasks
    m = _GITHUB_NUM_RE.match(task_id.strip())
    if m:
        number = m.group(1)
        for task in tasks:
            if task["id"].endswith(f"#{number}"):
                return task

    return None
