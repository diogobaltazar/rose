"""
Plan service — create recursive task structures with dependencies.

A plan is a parent task with child tasks linked via dependencies.
Children can themselves have dependencies, creating a recursive structure.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from topgun.services.tasks import create_task
from topgun.cli.backlog import _read_config, _get_sources


@dataclass
class PlanTask:
    title: str
    about: str
    estimated_minutes: int = 60
    priority: str = "medium"
    best_before: str | None = None
    must_before: str | None = None
    tags: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    children: list[PlanTask] = field(default_factory=list)


@dataclass
class CreatedTask:
    id: str
    title: str
    source_type: str
    url: str | None = None
    children: list[CreatedTask] = field(default_factory=list)


def create_plan_github(plan: PlanTask, repo: str) -> CreatedTask:
    """Create a recursive plan as GitHub issues with dependency links."""
    created_children = []
    child_refs = []

    for child in plan.children:
        created = create_plan_github(child, repo)
        created_children.append(created)
        child_refs.append(f"- {created.id} {created.title}")

    deps_section = "\n".join(child_refs) if child_refs else "_none_"
    ac = "\n".join(f"- [ ] {c}" for c in plan.acceptance_criteria) or "- [ ] Done"

    body = f"""## About

{plan.about}

## Acceptance Criteria

{ac}

## Dependencies

{deps_section}

## Best Before

{plan.best_before or '_none_'}

## Must Before

{plan.must_before or '_none_'}
"""

    labels = []
    if plan.priority:
        labels.extend(["--label", f"priority:{plan.priority}"])

    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", plan.title,
        "--body", body,
    ] + labels

    result = subprocess.run(cmd, capture_output=True, text=True)
    url = result.stdout.strip() if result.returncode == 0 else None

    issue_num = ""
    if url:
        parts = url.rstrip("/").split("/")
        issue_num = f"#{parts[-1]}" if parts else ""

    return CreatedTask(
        id=issue_num,
        title=plan.title,
        source_type="github",
        url=url,
        children=created_children,
    )


def create_plan_obsidian(plan: PlanTask, vault_path: str) -> CreatedTask:
    """Create a recursive plan as Obsidian vault tasks with dependency links."""
    created_children = []
    child_refs = []

    for child in plan.children:
        created = create_plan_obsidian(child, vault_path)
        created_children.append(created)
        child_refs.append(created.title)

    structured = {
        "title": plan.title,
        "about": plan.about,
        "motivation": None,
        "acceptance_criteria": plan.acceptance_criteria or ["Done"],
        "best_before": plan.best_before,
        "must_before": plan.must_before,
        "priority": plan.priority,
        "tags": plan.tags,
        "estimated_minutes": plan.estimated_minutes,
    }

    task_dir = create_task(structured, vault_path)

    if child_refs:
        task_file = task_dir / "task.md"
        text = task_file.read_text(encoding="utf-8")
        text = text.replace("_none_\n\n## Best Before", "\n".join(f"- {r}" for r in child_refs) + "\n\n## Best Before")
        task_file.write_text(text, encoding="utf-8")

    return CreatedTask(
        id=f"obsidian:{vault_path}:{plan.title}",
        title=plan.title,
        source_type="obsidian",
        url=None,
        children=created_children,
    )


def plan_to_dict(plan: PlanTask) -> dict:
    return {
        "title": plan.title,
        "about": plan.about,
        "estimated_minutes": plan.estimated_minutes,
        "priority": plan.priority,
        "best_before": plan.best_before,
        "must_before": plan.must_before,
        "tags": plan.tags,
        "acceptance_criteria": plan.acceptance_criteria,
        "children": [plan_to_dict(c) for c in plan.children],
    }


def dict_to_plan(d: dict) -> PlanTask:
    return PlanTask(
        title=d["title"],
        about=d.get("about", ""),
        estimated_minutes=d.get("estimated_minutes", 60),
        priority=d.get("priority", "medium"),
        best_before=d.get("best_before"),
        must_before=d.get("must_before"),
        tags=d.get("tags", []),
        acceptance_criteria=d.get("acceptance_criteria", []),
        children=[dict_to_plan(c) for c in d.get("children", [])],
    )


def flatten_plan(plan: PlanTask) -> list[PlanTask]:
    """Return all tasks in dependency order (children before parents)."""
    result = []
    for child in plan.children:
        result.extend(flatten_plan(child))
    result.append(plan)
    return result
