"""
Task service — create, close, and query tasks.

Extracted from cli/task.py and cli/backlog.py so both the API and CLI
can share this logic.
"""

import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from topgun.cli.backlog import (
    _fetch_all,
    _get_sources,
    _resolve_vault_path,
    _parse_body_section,
    _TASK_RE,
    PRIORITY_ORDER,
)
from topgun.cli.timer_match import fetch_tasks, match, match_by_id, _uid


SORT_FIELDS = {"title", "priority", "due", "scheduled", "source", "state", "created_at"}


def list_tasks(
    *,
    search: str | None = None,
    sort: str | None = None,
    order: str = "asc",
    statuses: list[str] | None = None,
) -> list[dict]:
    if statuses is None:
        statuses = ["open"]

    sources = _get_sources()
    if not sources:
        return []

    if search:
        items = _search_tasks(sources, search, statuses)
    else:
        raw_items, _ = _fetch_all(sources, statuses=statuses)
        items = _normalize_items(raw_items)

    if sort and sort in SORT_FIELDS:
        items = _sort_items(items, sort, order)
    else:
        items = _sort_items(items, "priority", "asc")

    return items


def _search_tasks(sources: list[dict], keyword: str, statuses: list[str]) -> list[dict]:
    items: list[dict] = []

    for s in sources:
        if s["type"] == "github":
            items.extend(_search_github(s, keyword, statuses))
        elif s["type"] == "obsidian":
            from topgun.cli.backlog import _fetch_obsidian
            raw = _fetch_obsidian(s["path"], statuses=statuses)
            kw_lower = keyword.lower()
            filtered = [i for i in raw if kw_lower in i["title"].lower()]
            items.extend(_normalize_items(filtered))

    return items


def _search_github(source: dict, keyword: str, statuses: list[str]) -> list[dict]:
    token_env = source.get("token_env", "GITHUB_TOKEN")
    token = os.environ.get(token_env, "")
    if not token:
        return []

    repo = source["repo"]
    env = {**os.environ, "GITHUB_TOKEN": token}

    gh_state = "all"
    if statuses == ["open"]:
        gh_state = "open"
    elif statuses == ["closed"]:
        gh_state = "closed"

    state_qualifier = f"state:{gh_state}" if gh_state != "all" else ""
    search_query = f"{keyword} repo:{repo} is:issue {state_qualifier}".strip()

    result = subprocess.run(
        [
            "gh", "search", "issues",
            "--match", "title,body",
            search_query,
            "--json", "number,title,labels,createdAt,body,state,url",
            "--limit", "50",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        return []

    items = []
    for issue in json.loads(result.stdout or "[]"):
        state = "closed" if (issue.get("state") or "").upper() == "CLOSED" else "open"
        if state not in statuses and "all" not in statuses:
            continue

        priority = ""
        for label in issue.get("labels", []):
            name = label.get("name", "")
            lower = name.lower()
            if "high" in lower:
                priority = "high"
            elif "medium" in lower:
                priority = "medium"
            elif "low" in lower:
                priority = "low"

        body = issue.get("body") or ""
        must_before = _parse_body_section(body, "Must Before") or None
        best_before = _parse_body_section(body, "Best Before") or None

        source_id = f"github:{repo}#{issue['number']}"
        items.append({
            "uid": _uid(source_id),
            "id": source_id,
            "title": f"#{issue['number']} {issue['title']}",
            "source": "github",
            "source_full": repo,
            "priority": priority,
            "due": must_before or best_before or "",
            "scheduled": best_before or "",
            "state": state,
            "created_at": issue.get("createdAt", ""),
            "url": issue.get("url", f"https://github.com/{repo}/issues/{issue['number']}"),
        })

    return items


def _normalize_items(raw_items: list[dict]) -> list[dict]:
    from topgun.cli.timer_match import _task_id, _uid
    result = []
    for item in raw_items:
        source_id = _task_id(item)
        result.append({
            "uid": _uid(source_id),
            "id": source_id,
            "title": item["title"],
            "source": item["type"],
            "source_full": item.get("source_full", ""),
            "priority": item.get("priority", ""),
            "due": item.get("due", ""),
            "scheduled": item.get("due", ""),
            "state": item.get("state", "open"),
            "created_at": "",
            "url": item.get("url", ""),
        })
    return result


def _sort_items(items: list[dict], field: str, order: str) -> list[dict]:
    reverse = order == "desc"

    if field == "priority":
        key = lambda t: (PRIORITY_ORDER.get(t.get("priority", ""), 3), t.get("due") or "9999-99-99")
    elif field == "due":
        key = lambda t: t.get("due") or "9999-99-99"
    elif field == "scheduled":
        key = lambda t: t.get("scheduled") or "9999-99-99"
    elif field == "title":
        key = lambda t: t.get("title", "").lower()
    elif field == "source":
        key = lambda t: t.get("source_full", "")
    elif field == "state":
        key = lambda t: t.get("state", "")
    elif field == "created_at":
        key = lambda t: t.get("created_at") or ""
    else:
        key = lambda t: t.get("title", "").lower()

    return sorted(items, key=key, reverse=reverse)


def get_task(task_ref: str) -> dict | None:
    return match_by_id(task_ref)


def search_task(query: str) -> list[dict]:
    return match(query)


def close_task(task_id: str) -> bool:
    """Close a task by its source ID. Returns True on success."""
    if task_id.startswith("obsidian:"):
        return _close_obsidian_task(task_id)
    elif task_id.startswith("github:"):
        return _close_github_task(task_id)
    return False


def _close_obsidian_task(source_id: str) -> bool:
    parts = source_id.split(":", 2)
    if len(parts) < 3:
        return False
    vault_path = parts[1]
    task_title = parts[2]

    vault = _resolve_vault_path(vault_path)
    task_file: Path | None = None
    for md_file in vault.rglob("task.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in text.splitlines():
            if _TASK_RE.match(line):
                line_title = _TASK_RE.sub("", line).strip()
                if line_title == task_title:
                    task_file = md_file
                    break
        if task_file:
            break

    if task_file is None:
        return False

    text = task_file.read_text(encoding="utf-8")
    if "status: open" in text:
        text = text.replace("status: open", "status: closed", 1)
    elif "status:" in text:
        text = re.sub(r"(status:\s*)(\S+)", r"\1closed", text, count=1)
    else:
        text = text.replace("---\n", "---\nstatus: closed\n", 1)

    today = date.today().isoformat()
    text = text.rstrip() + f"\n\n✅ {today}\n"
    task_file.write_text(text, encoding="utf-8")
    return True


def _close_github_task(source_id: str) -> bool:
    m = re.match(r"github:([^#]+)#(\d+)", source_id)
    if not m:
        return False
    repo, number = m.group(1), m.group(2)
    result = subprocess.run(
        ["gh", "issue", "close", number, "--repo", repo],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def create_task(structured: dict, vault_path: str) -> Path:
    """Write a structured task to an Obsidian vault. Returns the task directory."""
    import unicodedata
    from topgun.cli.backlog import _resolve_vault_path

    vault = _resolve_vault_path(vault_path)
    today = date.today().isoformat()

    title = structured.get("title", "untitled")
    slug_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug_title = slug_title.lower()
    slug_title = re.sub(r"[^\w\s-]", "", slug_title)
    slug_title = re.sub(r"[\s_]+", "-", slug_title).strip("-")

    task_dir = vault / f"{today}-{slug_title}"
    task_dir.mkdir(parents=True, exist_ok=True)

    tags_list = structured.get("tags") or []
    tags_str = ", ".join(f'"{t}"' for t in tags_list)

    criteria = structured.get("acceptance_criteria") or []
    criteria_str = "\n".join(f"- [ ] {c}" for c in criteria) or "- [ ] Done"

    template = """\
---
date: {date}
tags: [{tags}]
status: open
priority: {priority}
---

# {title}

## About

{about}

## Motivation

{motivation}

## Acceptance Criteria

{criteria}

## Dependencies

_none_

## Best Before

{best_before}

## Must Before

{must_before}
"""
    content = template.format(
        date=today,
        tags=tags_str,
        priority=structured.get("priority") or "",
        title=structured.get("title", "Untitled"),
        about=structured.get("about") or "_none_",
        motivation=structured.get("motivation") or "_none_",
        criteria=criteria_str,
        best_before=structured.get("best_before") or "_none_",
        must_before=structured.get("must_before") or "_none_",
    )

    task_file = task_dir / "task.md"
    task_file.write_text(content, encoding="utf-8")
    return task_dir
