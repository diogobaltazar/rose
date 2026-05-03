"""Shared type definitions for the topgun SDK."""

from typing import TypedDict


class Task(TypedDict, total=False):
    id: str
    source_type: str
    source_repo: str | None
    source_description: str
    number: int | None
    title: str
    state: str
    created_at: str | None
    closed_at: str | None
    priority: str | None
    best_before: str | None
    must_before: str | None
    about: str | None
    motivation: str | None
    acceptance_criteria: list[str]
    dependencies: list[str]
    url: str | None
    file: str | None
    line: int | None


class TimerStatus(TypedDict, total=False):
    running: bool
    task_id: str
    task_title: str
    started_at: str
    elapsed_s: float


class TimerStopResult(TypedDict):
    task_id: str
    task_title: str
    started_at: str
    stopped_at: str
    elapsed_s: float
