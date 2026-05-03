"""Unit tests for plan creation service."""

import pytest
from pathlib import Path

from topgun.services.plans import (
    PlanTask,
    flatten_plan,
    create_plan_obsidian,
    plan_to_dict,
    dict_to_plan,
)


def test_flatten_simple_plan():
    """A plan with two children should flatten to 3 tasks (children first)."""
    plan = PlanTask(
        title="Learn Spanish",
        about="12-week plan",
        children=[
            PlanTask(title="Week 1: Basics", about="Vocabulary"),
            PlanTask(title="Week 2: Grammar", about="Verb conjugation"),
        ],
    )
    flat = flatten_plan(plan)
    assert len(flat) == 3
    assert flat[0].title == "Week 1: Basics"
    assert flat[1].title == "Week 2: Grammar"
    assert flat[2].title == "Learn Spanish"


def test_flatten_nested_plan():
    """Deeply nested plans should flatten recursively (deepest first)."""
    plan = PlanTask(
        title="Parent",
        about="Top level",
        children=[
            PlanTask(
                title="Phase 1",
                about="First phase",
                children=[
                    PlanTask(title="Step A", about="Detail"),
                    PlanTask(title="Step B", about="Detail"),
                ],
            ),
        ],
    )
    flat = flatten_plan(plan)
    assert len(flat) == 4
    assert flat[0].title == "Step A"
    assert flat[1].title == "Step B"
    assert flat[2].title == "Phase 1"
    assert flat[3].title == "Parent"


def test_plan_round_trip():
    """plan_to_dict → dict_to_plan should be lossless."""
    plan = PlanTask(
        title="Test Plan",
        about="A test",
        estimated_minutes=90,
        priority="high",
        best_before="2026-06-01",
        tags=["study"],
        children=[PlanTask(title="Child", about="Sub-task")],
    )
    d = plan_to_dict(plan)
    restored = dict_to_plan(d)
    assert restored.title == "Test Plan"
    assert restored.estimated_minutes == 90
    assert len(restored.children) == 1
    assert restored.children[0].title == "Child"


def test_create_plan_obsidian(tmp_path):
    """Creating an Obsidian plan should produce task files on disk."""
    plan = PlanTask(
        title="Fitness Plan",
        about="8-week running program",
        estimated_minutes=45,
        children=[
            PlanTask(title="Week 1 Run", about="Easy jog 20min", estimated_minutes=30),
            PlanTask(title="Week 2 Run", about="Intervals", estimated_minutes=35),
        ],
    )
    result = create_plan_obsidian(plan, str(tmp_path))
    assert result.title == "Fitness Plan"
    assert len(result.children) == 2

    md_files = list(tmp_path.rglob("task.md"))
    assert len(md_files) == 3
