"""
topgun task — unified task management and time tracking.

Replaces the separate `backlog` and `timer` commands. All task sources
(GitHub, Obsidian) and all time tracking operations live here.
"""

import json
import os
import re
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from typing import Optional

import click
import typer
from rich.console import Console
from rich.table import Table
from rich import box

from topgun.cli.backlog import (
    _fetch_all,
    _get_sources,
    _read_config,
    _write_config,
    _fetch_github_description,
    _resolve_vault_path,
    PRIORITY_COLOR,
    PRIORITY_ORDER,
    TYPE_COLOR,
)
from topgun.cli.timer_match import fetch_tasks, match, match_by_id, _uid

console = Console()
app = typer.Typer(
    name="task",
    help="Manage tasks and track time.",
    add_completion=False,
    invoke_without_command=True,
)

TIMER_LOG = Path(os.environ.get("TOPGUN_TIMER_LOG", str(Path.home() / ".topgun" / "timer.jsonl")))

_EDITOR_TEMPLATE = """\
# What are you working on?
# Describe the task below — save and close when done.
# Lines starting with '#' are ignored.

"""


@app.callback()
def _help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _type_tag(t: str) -> str:
    color = TYPE_COLOR.get(t, "white")
    return f"[{color}]{t}[/{color}]"


def _due_color(due: str | None) -> str:
    """Return a Rich color tag for a due date based on urgency."""
    if not due:
        return "dim"
    try:
        delta = (date.fromisoformat(due) - date.today()).days
    except ValueError:
        return "dim"
    if delta < 0:
        return "bold red"
    if delta == 0:
        return "red"
    if delta <= 3:
        return "color(202)"   # orange-red
    if delta <= 7:
        return "color(208)"   # orange
    if delta <= 14:
        return "yellow"
    return "green"


def _fmt_duration(seconds: float) -> str:
    total_m = int(seconds // 60)
    h, m = divmod(total_m, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {int(seconds % 60):02d}s"


def _fmt_dt(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso).astimezone()
        return dt.strftime("%d-%b-%Y %H:%M")
    except Exception:
        return iso[:16]


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
    """Return the most recent unmatched start event, or None."""
    last_start = None
    for e in _read_events():
        if e["event"] == "start":
            last_start = e
        elif e["event"] == "stop":
            last_start = None
    return last_start


def _elapsed_seconds(start_ts: str) -> float:
    t0 = datetime.fromisoformat(start_ts)
    return (datetime.now(timezone.utc) - t0).total_seconds()


def _totals_by_task_id() -> dict[str, float]:
    """Return accumulated seconds per task_id from the event log."""
    totals: dict[str, float] = {}
    open_start: dict | None = None
    for e in _read_events():
        if e["event"] == "start":
            open_start = e
        elif e["event"] == "stop" and open_start:
            t0 = datetime.fromisoformat(open_start["ts"])
            t1 = datetime.fromisoformat(e["ts"])
            tid = open_start["task_id"]
            totals[tid] = totals.get(tid, 0) + (t1 - t0).total_seconds()
            open_start = None
    if open_start:
        tid = open_start["task_id"]
        totals[tid] = totals.get(tid, 0) + _elapsed_seconds(open_start["ts"])
    return totals


def _intervals_by_task_id(task_id: str) -> list[dict]:
    """Return list of {start, end, duration_s} for a given task_id."""
    intervals = []
    open_start: dict | None = None
    for e in _read_events():
        if e["event"] == "start" and e["task_id"] == task_id:
            open_start = e
        elif e["event"] == "stop" and open_start and open_start["task_id"] == task_id:
            t0 = datetime.fromisoformat(open_start["ts"])
            t1 = datetime.fromisoformat(e["ts"])
            intervals.append({
                "start": open_start["ts"],
                "end": e["ts"],
                "duration_s": (t1 - t0).total_seconds(),
            })
            open_start = None
    if open_start:
        intervals.append({
            "start": open_start["ts"],
            "end": None,
            "duration_s": _elapsed_seconds(open_start["ts"]),
        })
    return intervals


# ---------------------------------------------------------------------------
# Task resolution
# ---------------------------------------------------------------------------

def _editor_query() -> str | None:
    """Open $EDITOR and return the user's task description, or None if empty."""
    text = click.edit(_EDITOR_TEMPLATE)
    if not text:
        return None
    lines = [l for l in text.splitlines() if not l.startswith("#")]
    query = " ".join(lines).strip()
    return query or None


def _is_structured_id(ref: str) -> bool:
    """Return True if *ref* looks like a UID, source ID, or bare issue number."""
    from topgun.cli.timer_match import _UID_RE, _GITHUB_NUM_RE

    if _UID_RE.match(ref):
        return True
    if _GITHUB_NUM_RE.match(ref.strip()):
        return True
    if ":" in ref:          # source IDs contain a colon, e.g. "github:owner/repo#1"
        return True
    return False


def _resolve_task(task_arg: str) -> dict:
    """Resolve task by UID, source ID, bare issue number, or fuzzy description."""
    task = match_by_id(task_arg)
    if task:
        return task

    if _is_structured_id(task_arg):
        console.print(f"[yellow]no task found for id:[/yellow] {task_arg}")
        raise typer.Exit(1)

    console.print(f"[dim]searching for:[/dim] {task_arg}")
    candidates = match(task_arg)

    if not candidates:
        console.print("[yellow]no matching tasks found[/yellow]")
        raise typer.Exit(1)

    if len(candidates) == 1:
        task = candidates[0]
        console.print(f"[dim]matched:[/dim] [cyan]{task['title']}[/cyan]")
        return task

    console.print("\n[bold]Multiple matches — select a task:[/bold]\n")
    for i, c in enumerate(candidates, 1):
        score_pct = f"{int(c.get('score', 0) * 100)}%"
        console.print(f"  [dim]{i}[/dim]  [cyan]{c['title']}[/cyan]  [dim]{score_pct}[/dim]")

    console.print()
    raw = typer.prompt("task #", default="1")
    try:
        idx = int(raw.strip()) - 1
        assert 0 <= idx < len(candidates)
    except (ValueError, AssertionError):
        console.print("[red]invalid selection[/red]")
        raise typer.Exit(1)

    return candidates[idx]


# ---------------------------------------------------------------------------
# Commands — time tracking
# ---------------------------------------------------------------------------

@app.command("start")
def start(
    task: Optional[str] = typer.Option(None, "--task", "-t", help="UID, issue number, or description"),
):
    """Start recording time. Opens $EDITOR if --task is not given."""
    active = _active_period()
    if active:
        elapsed = _fmt_duration(_elapsed_seconds(active["ts"]))
        console.print(
            f"[yellow]timer already running[/yellow] — {active['task_title']} ({elapsed})\n"
            f"run [bold]topgun task stop[/bold] first"
        )
        raise typer.Exit(1)

    if task is None:
        task = _editor_query()
        if not task:
            console.print("[yellow]no description entered — cancelled[/yellow]")
            raise typer.Exit(1)

    resolved = _resolve_task(task)
    _append_event("start", resolved["id"], resolved["title"])
    console.print(f"[green]started[/green]  [cyan]{resolved['title']}[/cyan]  [dim]{resolved['uid']}[/dim]")


@app.command("stop")
def stop():
    """Stop the current timer."""
    active = _active_period()
    if not active:
        console.print("[yellow]no timer running[/yellow]")
        raise typer.Exit(1)

    elapsed = _fmt_duration(_elapsed_seconds(active["ts"]))
    _append_event("stop", active["task_id"], active["task_title"])
    console.print(f"[green]stopped[/green]  [cyan]{active['task_title']}[/cyan]  [dim]{elapsed}[/dim]")


@app.command("status")
def status():
    """Show the currently running timer."""
    active = _active_period()
    if not active:
        console.print("[dim]no timer running[/dim]")
        return
    elapsed = _fmt_duration(_elapsed_seconds(active["ts"]))
    uid = _uid(active["task_id"])
    console.print(f"[green]●[/green]  [cyan]{active['task_title']}[/cyan]  [bold]{elapsed}[/bold]  [dim]{uid}[/dim]")


# ---------------------------------------------------------------------------
# Commands — task list and detail
# ---------------------------------------------------------------------------

def _list_sort_key(t: dict) -> tuple:
    due = t.get("due") or ""
    return (due or "9999-99-99", t.get("source_full", ""), t["title"])


def _parse_filter(filter_str: str) -> list[str]:
    """Parse '--filter status=open,closed' into a list of status strings."""
    statuses = []
    for part in filter_str.split(","):
        part = part.strip()
        if "=" in part:
            key, _, val = part.partition("=")
            if key.strip() == "status":
                statuses.extend(v.strip() for v in val.split(",") if v.strip())
        else:
            # Bare value, treat as status directly.
            if part:
                statuses.append(part)
    return statuses or ["open"]


@app.command("list")
def list_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show source path column"),
    filter: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter e.g. status=open,closed"),
):
    """List tasks with accumulated time where recorded. Defaults to open tasks only."""
    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun task track")
        raise typer.Exit()

    statuses = _parse_filter(filter) if filter else ["open"]
    show_status = len(statuses) > 1

    tasks = fetch_tasks(statuses=statuses)
    if not tasks:
        label = "/".join(statuses)
        console.print(f"[dim]no {label} tasks found[/dim]")
        return

    totals = _totals_by_task_id()
    active = _active_period()
    active_id = active["task_id"] if active else None

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", pad_edge=False)
    table.add_column("UID", style="dim", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    table.add_column("Title")
    table.add_column("Due", width=12, no_wrap=True)
    if show_status:
        table.add_column("Status", width=10, no_wrap=True)
    table.add_column("Time", justify="right")
    if verbose:
        table.add_column("Source", style="dim")

    _STATUS_COLOR = {"open": "green", "closed": "dim", "inprogress": "yellow"}

    has_links = False
    for t in sorted(tasks, key=_list_sort_key):
        seconds = totals.get(t["id"])
        time_str = _fmt_duration(seconds) if seconds else "—"
        marker = " [green]●[/green]" if t["id"] == active_id else ""

        due = t.get("due", "")
        dc = _due_color(due)
        due_cell = f"[{dc}]{due}[/{dc}]" if due else "[dim]—[/dim]"

        url = t.get("url", "")
        if url:
            has_links = True
            title_cell = f"{t['title']} [link={url}][dim]↗[/dim][/link]"
        else:
            title_cell = t["title"]

        row = [t["uid"], _type_tag(t["source"]), title_cell, due_cell]
        if show_status:
            st = t.get("state", "open")
            sc = _STATUS_COLOR.get(st, "dim")
            row.append(f"[{sc}]{st}[/{sc}]")
        row.append(f"{time_str}{marker}")
        if verbose:
            row.append(t.get("source_full", ""))
        table.add_row(*row)

    console.print(table)
    if has_links:
        console.print("[dim]  ↗ click to open task in browser or Obsidian[/dim]")


@app.command("show")
def show(
    task: str = typer.Option(..., "--task", "-t", help="Task UID or issue number"),
):
    """Show task details and time intervals."""
    resolved = match_by_id(task)
    if not resolved:
        console.print(f"[yellow]task not found:[/yellow] {task}")
        raise typer.Exit(1)

    intervals = _intervals_by_task_id(resolved["id"])
    uid = resolved["uid"]
    total_s = sum(i["duration_s"] for i in intervals)

    url = resolved.get("url", "")
    title_str = f"[link={url}]{resolved['title']}[/link]" if url else f"[cyan]{resolved['title']}[/cyan]"

    console.print(f"\n  [dim]uid[/dim]     {uid}")
    console.print(f"  [dim]source[/dim]  {resolved['id']}")
    console.print(f"  [dim]title[/dim]   {title_str}")
    if url:
        console.print(f"  [dim]url[/dim]     [dim]{url}[/dim]")
    console.print()

    if not intervals:
        console.print("  [dim]no time recorded for this task[/dim]\n")
        return

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold", pad_edge=False)
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Duration", justify="right")

    for iv in intervals:
        end_str = _fmt_dt(iv["end"]) if iv["end"] else "[green]running[/green]"
        table.add_row(_fmt_dt(iv["start"]), end_str, _fmt_duration(iv["duration_s"]))

    console.print(table)
    console.print(f"\n  [bold]Total[/bold]  {_fmt_duration(total_s)}\n")


# ---------------------------------------------------------------------------
# Commands — task creation and closing
# ---------------------------------------------------------------------------

_ADD_EDITOR_TEMPLATE = """\
# New task — describe it below in plain language.
# Include: what you want to do, why, any deadlines, and priority.
# Lines starting with '#' are ignored.

"""

_OBSIDIAN_TASK_TEMPLATE = """\
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


def _slugify(title: str) -> str:
    import unicodedata
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    title = title.lower()
    title = re.sub(r"[^\w\s-]", "", title)
    title = re.sub(r"[\s_]+", "-", title).strip("-")
    return title


def _write_obsidian_task(vault_path: str, structured: dict) -> Path:
    """Write a new task.md to the vault. Returns the task directory path."""
    vault = _resolve_vault_path(vault_path)
    today = date.today().isoformat()
    slug = _slugify(structured.get("title", "untitled"))
    task_dir = vault / f"{today}-{slug}"
    task_dir.mkdir(parents=True, exist_ok=True)

    tags_list = structured.get("tags") or []
    tags_str = ", ".join(f'"{t}"' for t in tags_list)

    criteria = structured.get("acceptance_criteria") or []
    criteria_str = "\n".join(f"- [ ] {c}" for c in criteria) or "- [ ] Done"

    content = _OBSIDIAN_TASK_TEMPLATE.format(
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


@app.command("add")
def add():
    """Create a new task. Select a source, describe the task in $EDITOR."""
    import sys
    from urllib.parse import quote

    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun task track")
        raise typer.Exit()

    obsidian_sources = [s for s in sources if s["type"] == "obsidian"]
    github_sources = [s for s in sources if s["type"] == "github"]

    if not obsidian_sources:
        console.print("[yellow]no Obsidian sources tracked — run: topgun task track --type obsidian[/yellow]")
        raise typer.Exit(1)

    console.print()
    console.print("[bold]Select a source:[/bold]\n")

    numbered: list[dict] = []
    for idx, s in enumerate(obsidian_sources, 1):
        label = s.get("path", "?")
        desc = s.get("description", "")
        console.print(f"  [dim]{idx}[/dim]  [magenta]obsidian[/magenta]  [cyan]{label}[/cyan]  [dim]{desc}[/dim]")
        numbered.append(s)
    for s in github_sources:
        label = s.get("repo", "?")
        desc = s.get("description", "")
        console.print(f"      [dim]github[/dim]    [dim]{label}[/dim]  [dim]{desc}  [unavailable][/dim]")

    console.print()
    raw = typer.prompt("source #", default="1")
    try:
        choice_idx = int(raw.strip()) - 1
        assert 0 <= choice_idx < len(numbered)
    except (ValueError, AssertionError):
        console.print("[red]invalid selection[/red]")
        raise typer.Exit(1)
    chosen = numbered[choice_idx]

    # Erase source list and prompt; replace with a single compact line.
    # Lines printed: blank(1) + "Select a source:\n"(2) + sources + blank(1) + prompt(1)
    n_erase = 5 + len(obsidian_sources) + len(github_sources)
    sys.stdout.write(f"\033[{n_erase}A\033[J")
    sys.stdout.flush()
    console.print(
        f"  [magenta]obsidian[/magenta]  "
        f"[cyan]{chosen.get('description', chosen.get('path', '?'))}[/cyan]"
    )

    today = date.today().isoformat()
    text = click.edit(_ADD_EDITOR_TEMPLATE)
    if not text:
        console.print("[yellow]no input — cancelled[/yellow]")
        raise typer.Exit(1)
    lines = [l for l in text.splitlines() if not l.startswith("#")]
    description = " ".join(lines).strip()
    if not description:
        console.print("[yellow]no description entered — cancelled[/yellow]")
        raise typer.Exit(1)

    from topgun.inference.anthropic import call, load_prompt
    system = load_prompt("task_add")
    user_msg = f"Today's date: {today}\n\nTask description:\n{description}"
    raw_json = call(prompt=user_msg, system=system, command="task_add", status_message="structuring task…")

    # Strip markdown code fences if the model wrapped the JSON.
    clean = raw_json.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-z]*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean.rstrip())

    try:
        structured = json.loads(clean)
    except json.JSONDecodeError:
        console.print("[red]could not parse model response — task not saved[/red]")
        console.print(f"[dim]{raw_json}[/dim]")
        raise typer.Exit(1)

    task_dir = _write_obsidian_task(chosen["path"], structured)

    # Use vault+file URL format — avoids VSCode's terminal file-path detector
    # hijacking the click when an absolute path appears in the URL.
    vault_name = Path(chosen["path"]).name
    relative_file = quote(f"{task_dir.name}/task.md")
    obs_url = f"obsidian://open?vault={quote(vault_name)}&file={relative_file}"
    title = structured.get("title", "Untitled")
    console.print(f"[green]created[/green]  [link={obs_url}]{title}[/link]")


@app.command("close")
def close(
    task_ref: Optional[str] = typer.Argument(None, help="Task UID, issue number, source ID, or description"),
):
    """Close a task. Accepts a UID/issue number, or uses fuzzy search if omitted."""
    if task_ref:
        resolved = _resolve_task(task_ref)
    else:
        query = _editor_query()
        if not query:
            console.print("[yellow]no description entered — cancelled[/yellow]")
            raise typer.Exit(1)
        resolved = _resolve_task(query)

    source_id: str = resolved["id"]

    if source_id.startswith("obsidian:"):
        # Derive the vault path and task directory from the source ID.
        # Format: "obsidian:<vault_path>:<title>"
        parts = source_id.split(":", 2)
        if len(parts) < 3:
            console.print(f"[red]cannot parse obsidian source ID:[/red] {source_id}")
            raise typer.Exit(1)
        vault_path = parts[1]
        task_title = parts[2]

        # Locate the task.md file by searching for a directory whose task.md
        # contains an Acceptance Criteria checkbox with a matching title.
        vault = _resolve_vault_path(vault_path)
        task_file: Path | None = None
        for md_file in vault.rglob("task.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for line in text.splitlines():
                from topgun.cli.backlog import _TASK_RE
                if _TASK_RE.match(line):
                    line_title = _TASK_RE.sub("", line).strip()
                    if line_title == task_title:
                        task_file = md_file
                        break
            if task_file:
                break

        if task_file is None:
            console.print(f"[yellow]task file not found for:[/yellow] {task_title}")
            raise typer.Exit(1)

        text = task_file.read_text(encoding="utf-8")
        # Update status in frontmatter.
        if "status: open" in text:
            text = text.replace("status: open", "status: closed", 1)
        elif "status:" in text:
            text = re.sub(r"(status:\s*)(\S+)", r"\1closed", text, count=1)
        else:
            # Append status to frontmatter if missing.
            text = text.replace("---\n", "---\nstatus: closed\n", 1)

        today = date.today().isoformat()
        text = text.rstrip() + f"\n\n✅ {today}\n"
        task_file.write_text(text, encoding="utf-8")
        console.print(f"[green]closed[/green]  [cyan]{resolved['title']}[/cyan]")

    elif source_id.startswith("github:"):
        # Format: "github:<owner/repo>#<number>"
        m = re.match(r"github:([^#]+)#(\d+)", source_id)
        if not m:
            console.print(f"[red]cannot parse github source ID:[/red] {source_id}")
            raise typer.Exit(1)
        repo, number = m.group(1), m.group(2)
        import subprocess as _sp
        result = _sp.run(
            ["gh", "issue", "close", number, "--repo", repo],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            console.print(f"[red]gh issue close failed:[/red] {err}")
            raise typer.Exit(1)
        console.print(f"[green]closed[/green]  [cyan]{resolved['title']}[/cyan]")

    else:
        console.print(f"[yellow]unknown source type for:[/yellow] {source_id}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Commands — source management (formerly topgun backlog)
# ---------------------------------------------------------------------------

@app.command("track")
def track(
    type: str = typer.Option(None, "--type", "-t", help="github or obsidian"),
    repo: str = typer.Option(None, "--repo", help="GitHub repo (owner/repo)"),
    path: str = typer.Option(None, "--path", help="Obsidian vault path"),
    description: str = typer.Option(None, "--description", "-d", help="Description"),
    token_env: str = typer.Option(None, "--token-env", help="Token env var (github only)"),
):
    """Add a task source (GitHub repo or Obsidian vault)."""
    data = _read_config()
    sources = data.setdefault("backlog", {}).setdefault("sources", [])

    if type is None:
        typer.echo("source type: [1] github  [2] obsidian")
        choice = typer.prompt("type", default="1")
        type = "github" if choice == "1" else "obsidian" if choice == "2" else None
        if type is None:
            typer.echo("error: invalid choice", err=True)
            raise typer.Exit(1)

    if type == "github":
        repo = repo or typer.prompt("GitHub repo (owner/repo)").strip()
        token_env = token_env or typer.prompt("Token env var", default="GITHUB_TOKEN").strip()
        if description is None:
            description = typer.prompt("Description", default="").strip() or _fetch_github_description(repo, token_env)
        entry = {"type": "github", "repo": repo, "description": description, "token_env": token_env}
        duplicate = any(s.get("type") == "github" and s.get("repo") == repo for s in sources)
    elif type == "obsidian":
        from pathlib import Path as _Path
        raw = path or typer.prompt("Vault path").strip()
        resolved_path = str(_Path(raw).expanduser().resolve())
        if description is None:
            description = typer.prompt("Description", default="").strip()
        entry = {"type": "obsidian", "path": resolved_path, "description": description}
        duplicate = any(s.get("type") == "obsidian" and s.get("path") == resolved_path for s in sources)
    else:
        typer.echo("error: type must be github or obsidian", err=True)
        raise typer.Exit(1)

    if duplicate:
        typer.echo("already tracked")
        raise typer.Exit()

    sources.append(entry)
    _write_config(data)
    label = entry.get("repo") or entry.get("path")
    console.print(f"[green]ok[/green]  {_type_tag(entry['type'])}\t[cyan]{label}[/cyan]")
    if entry["type"] == "github" and not os.environ.get(entry["token_env"]):
        console.print(f"[yellow]add to ~/.zshrc:[/yellow]  export {entry['token_env']}=$(gh auth token)")


@app.command("untrack")
def untrack():
    """Remove a task source."""
    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun task track")
        raise typer.Exit()

    for i, s in enumerate(sources, 1):
        label = s.get("repo") or s.get("path", "?")
        console.print(f"  [dim]{i}[/dim]  {_type_tag(s['type'])}\t{label}")

    raw = typer.prompt("remove #")
    try:
        idx = int(raw.strip()) - 1
        assert 0 <= idx < len(sources)
    except (ValueError, AssertionError):
        typer.echo("error: invalid selection", err=True)
        raise typer.Exit(1)

    removed = sources.pop(idx)
    data = _read_config()
    data.setdefault("backlog", {})["sources"] = sources
    _write_config(data)
    label = removed.get("repo") or removed.get("path", "?")
    console.print(f"[green]ok[/green]  removed [cyan]{label}[/cyan]")


@app.command("sources")
def sources_cmd():
    """List all tracked task sources."""
    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun task track")
        raise typer.Exit()

    for s in sources:
        label = s.get("repo") or s.get("path", "?")
        desc = s.get("description", "")
        console.print(f"  {_type_tag(s['type'])}\t[cyan]{label}[/cyan]\t[dim]{desc}[/dim]")
