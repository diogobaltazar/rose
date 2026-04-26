"""
Task matching for topgun task.

Fetches open tasks from all configured backlog sources and uses Claude Haiku
to fuzzy-match a natural language query against them, returning ranked candidates.
"""

import hashlib
import json
import re

from topgun.cli.backlog import _fetch_all, _get_sources
from topgun.inference.anthropic import call, load_prompt

_GITHUB_NUM_RE = re.compile(r"^#?(\d+)$")


def _uid(source_id: str) -> str:
    """Derive a stable topgun UID from a source identity string."""
    return "tg-" + hashlib.sha256(source_id.encode()).hexdigest()[:8]


def _task_id(item: dict) -> str:
    """Derive a stable source identity string from a backlog item."""
    if item["type"] == "github":
        m = re.match(r"^#(\d+)\s", item["title"])
        number = m.group(1) if m else "?"
        return f"github:{item['source_full']}#{number}"
    return f"obsidian:{item['source_full']}:{item['title']}"


def fetch_tasks() -> list[dict]:
    """Return all open backlog tasks as {uid, id, title, source} dicts."""
    sources = _get_sources()
    if not sources:
        return []
    items, _ = _fetch_all(sources)
    result = []
    for item in items:
        source_id = _task_id(item)
        result.append({
            "uid": _uid(source_id),
            "id": source_id,
            "title": item["title"],
            "source": item["type"],
            "source_full": item.get("source_full", ""),
        })
    return result


def match(query: str) -> list[dict]:
    """
    Return ranked task candidates matching the natural language query.

    Returns a list of dicts: [{uid, id, title, source, score}, ...], at most 5.
    Returns an empty list if no tasks are configured or nothing matches.
    """
    tasks = fetch_tasks()
    if not tasks:
        return []

    task_lines = "\n".join(
        f'{t["uid"]} | {t["id"]} | {t["source"]} | {t["title"]}' for t in tasks
    )
    user_message = f"Tasks:\n{task_lines}\n\nQuery: {query}"

    system = load_prompt("timer_match")
    raw = call(prompt=user_message, system=system, command="task")

    try:
        candidates = json.loads(raw)
        if not isinstance(candidates, list):
            return []
        # Enrich candidates with uid from our task list for consistency
        uid_map = {t["id"]: t for t in tasks}
        for c in candidates:
            if c.get("id") in uid_map:
                c.setdefault("uid", uid_map[c["id"]]["uid"])
        return candidates
    except json.JSONDecodeError:
        return []


def match_by_id(task_ref: str) -> dict | None:
    """
    Look up a task without an SDK call.

    Accepts:
    - topgun UID:    "tg-a3f2c1b4"
    - bare number:   "127" or "#127"  (GitHub issues)
    - full source ID: "github:owner/repo#127"
    """
    tasks = fetch_tasks()

    # UID match
    if task_ref.startswith("tg-"):
        for task in tasks:
            if task["uid"] == task_ref:
                return task
        return None

    # Full source ID match
    for task in tasks:
        if task["id"] == task_ref:
            return task

    # Bare number match against GitHub tasks
    m = _GITHUB_NUM_RE.match(task_ref.strip())
    if m:
        number = m.group(1)
        for task in tasks:
            if task["id"].endswith(f"#{number}"):
                return task

    return None
