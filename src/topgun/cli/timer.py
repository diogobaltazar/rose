"""
topgun timer — track time spent per task.

Events are appended to ~/.topgun/timer.jsonl as an append-only log.
Each line is either a `start` or `stop` event with a task ID and ISO timestamp.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import typer

from topgun.cli.theme import console, make_table, SAGE, SMOKE, LEAF, WARN, ERR, PEARL
from topgun.cli.timer_match import match, match_by_id
app = typer.Typer(name="timer", help="Track time spent per task.", add_completion=False, invoke_without_command=True)

TIMER_LOG = Path(os.environ.get("TOPGUN_TIMER_LOG", str(Path.home() / ".topgun" / "timer.jsonl")))


@app.callback()
def _timer_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Event log helpers
# ---------------------------------------------------------------------------

def _append_event(event: str, task_id: str, task_title: str) -> None:
    TIMER_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "task_id": task_id,
        "task_title": task_title,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with TIMER_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


def _read_events() -> list[dict]:
    if not TIMER_LOG.exists():
        return []
    events = []
    with TIMER_LOG.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _active_period() -> dict | None:
    """Return the most recent unmatched start event, or None if no period is open."""
    last_start = None
    for e in _read_events():
        if e["event"] == "start":
            last_start = e
        elif e["event"] == "stop":
            last_start = None
    return last_start


def _elapsed_seconds(start_ts: str) -> float:
    t0 = datetime.fromisoformat(start_ts)
    now = datetime.now(timezone.utc)
    return (now - t0).total_seconds()


def _fmt_duration(seconds: float) -> str:
    total_m = int(seconds // 60)
    h, m = divmod(total_m, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {int(seconds % 60):02d}s"


# ---------------------------------------------------------------------------
# Task resolution
# ---------------------------------------------------------------------------

def _resolve_task(task_arg: str) -> dict:
    """
    Resolve the target task from --task argument.

    Returns {id, title, source} or raises typer.Exit on failure.
    """
    # 1. Explicit ID — direct lookup, no SDK call
    task = match_by_id(task_arg)
    if task:
        return task

    # 3. Natural language — fuzzy match via Claude Haiku
    console.print(f"[{SMOKE}]searching for:[/{SMOKE}] {task_arg}")
    candidates = match(task_arg)

    if not candidates:
        console.print(f"[{WARN}]no matching tasks found[/{WARN}]")
        raise typer.Exit(1)

    if len(candidates) == 1:
        task = candidates[0]
        console.print(f"[{SMOKE}]matched:[/{SMOKE}] [{SAGE}]{task['title']}[/{SAGE}]")
        return task

    console.print(f"\n[{PEARL}]Multiple matches:[/{PEARL}]\n")
    for i, c in enumerate(candidates, 1):
        score_pct = f"{int(c.get('score', 0) * 100)}%"
        console.print(f"  [{SMOKE}]{i}[/{SMOKE}]  [{SAGE}]{c['title']}[/{SAGE}]  [{SMOKE}]{score_pct}[/{SMOKE}]")

    console.print()
    raw = typer.prompt("task #", default="1")
    try:
        idx = int(raw.strip()) - 1
        assert 0 <= idx < len(candidates)
    except (ValueError, AssertionError):
        console.print(f"[{ERR}]invalid selection[/{ERR}]")
        raise typer.Exit(1)

    return candidates[idx]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("start")
def start(
    task: str = typer.Option(..., "--task", "-t", help="Task ID, issue number, or description"),
):
    """Start recording time for a task."""
    active = _active_period()
    if active:
        elapsed = _fmt_duration(_elapsed_seconds(active["ts"]))
        console.print(
            f"[{WARN}]timer already running[/{WARN}] — {active['task_title']} ({elapsed})\n"
            f"run topgun timer stop first"
        )
        raise typer.Exit(1)

    resolved = _resolve_task(task)
    _append_event("start", resolved["id"], resolved["title"])
    console.print(f"[{LEAF}]started[/{LEAF}]  [{SAGE}]{resolved['title']}[/{SAGE}]")


@app.command("stop")
def stop():
    """Stop the current timer."""
    active = _active_period()
    if not active:
        console.print(f"[{WARN}]no timer running[/{WARN}]")
        raise typer.Exit(1)

    elapsed = _fmt_duration(_elapsed_seconds(active["ts"]))
    _append_event("stop", active["task_id"], active["task_title"])
    console.print(f"[{LEAF}]stopped[/{LEAF}]  [{SAGE}]{active['task_title']}[/{SAGE}]  [{SMOKE}]{elapsed}[/{SMOKE}]")


@app.command("status")
def status():
    """Show the currently running timer."""
    active = _active_period()
    if not active:
        console.print(f"[{SMOKE}]no timer running[/{SMOKE}]")
        return

    elapsed = _fmt_duration(_elapsed_seconds(active["ts"]))
    console.print(f"[{LEAF}]●[/{LEAF}]  [{SAGE}]{active['task_title']}[/{SAGE}]  [{PEARL}]{elapsed}[/{PEARL}]")


@app.command("report")
def report():
    """Show total time spent per task."""
    events = _read_events()
    if not events:
        console.print(f"[{SMOKE}]no time recorded yet[/{SMOKE}]")
        return

    # Pair start/stop events and accumulate per task
    totals: dict[str, float] = {}
    titles: dict[str, str] = {}
    open_start: dict | None = None

    for e in events:
        if e["event"] == "start":
            open_start = e
            titles[e["task_id"]] = e["task_title"]
        elif e["event"] == "stop" and open_start:
            t0 = datetime.fromisoformat(open_start["ts"])
            t1 = datetime.fromisoformat(e["ts"])
            duration = (t1 - t0).total_seconds()
            totals[open_start["task_id"]] = totals.get(open_start["task_id"], 0) + duration
            open_start = None

    # Include any open period as in-progress
    if open_start:
        in_progress_id = open_start["task_id"]
        elapsed = _elapsed_seconds(open_start["ts"])
        totals[in_progress_id] = totals.get(in_progress_id, 0) + elapsed
        titles[in_progress_id] = open_start["task_title"]

    if not totals:
        console.print(f"[{SMOKE}]no completed periods yet[/{SMOKE}]")
        return

    table = make_table(
        ("Task", {}),
        ("Time", {"justify": "right"}),
    )

    for task_id, seconds in sorted(totals.items(), key=lambda x: -x[1]):
        title = titles.get(task_id, task_id)
        marker = f" [{LEAF}]●[/{LEAF}]" if open_start and task_id == open_start.get("task_id") else ""
        table.add_row(f"{title}{marker}", _fmt_duration(seconds))

    console.print(table)
