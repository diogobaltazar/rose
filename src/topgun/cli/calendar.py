"""
topgun calendar — Apple Calendar integration via CalDAV.
"""

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from topgun.cli.backlog import _read_config, _write_config

console = Console()
app = typer.Typer(
    name="calendar",
    help="Apple Calendar integration.",
    add_completion=False,
    invoke_without_command=True,
)


@app.callback()
def _help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("setup")
def setup():
    """Configure iCloud calendar credentials."""
    console.print("\n[bold]Apple Calendar Setup[/bold]\n")
    console.print("[dim]Generate an app-specific password at appleid.apple.com[/dim]\n")

    username = typer.prompt("iCloud email")
    password = typer.prompt("App-specific password", hide_input=True)
    calendar_name = typer.prompt("Calendar name", default="Topgun")

    from topgun.services.calendar import CalendarService
    svc = CalendarService(username=username, password=password, calendar_name=calendar_name)

    with console.status("Connecting to iCloud…"):
        connected = svc.connect()

    if not connected:
        console.print("[red]Connection failed.[/red] Check your credentials.")
        raise typer.Exit(1)

    with console.status("Finding calendar…"):
        cal = svc.get_or_create_calendar()

    if not cal:
        console.print("[red]Could not find or create calendar.[/red]")
        raise typer.Exit(1)

    data = _read_config()
    data.setdefault("calendar", {}).update({
        "enabled": True,
        "provider": "icloud",
        "username": username,
        "password": password,
        "calendar_name": calendar_name,
        "available_hours": {"start": "20:00", "end": "05:00"},
        "buffer_minutes": 30,
        "default_duration_minutes": 60,
    })
    _write_config(data)

    console.print(f"[green]Connected[/green]  Calendar: [cyan]{calendar_name}[/cyan]")


@app.command("status")
def status():
    """Show calendar sync status."""
    from topgun.services.calendar import CalendarService
    svc = CalendarService()
    connected = svc.connect()

    if connected:
        svc.get_or_create_calendar()
    st = svc.get_status()

    console.print(f"\n  [dim]connected[/dim]   {'[green]yes[/green]' if connected else '[red]no[/red]'}")
    console.print(f"  [dim]calendar[/dim]    [cyan]{st.get('calendar_name', '—')}[/cyan]")
    console.print(f"  [dim]events[/dim]      {st.get('scheduled_events', 0)}")
    console.print(f"  [dim]sync token[/dim]  [dim]{(st.get('sync_token') or '—')[:20]}…[/dim]")
    console.print()

    events = st.get("events", {})
    if events:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold", pad_edge=False)
        table.add_column("Task")
        table.add_column("Start")
        table.add_column("End")
        table.add_column("Modified")

        for tid, ev in events.items():
            modified = "[yellow]yes[/yellow]" if ev.get("user_modified") else "[dim]no[/dim]"
            table.add_row(
                tid[:40],
                ev.get("scheduled_start", "—")[:16],
                ev.get("scheduled_end", "—")[:16],
                modified,
            )
        console.print(table)


@app.command("sync")
def sync():
    """Sync with Apple Calendar (detect user edits)."""
    from topgun.services.calendar import CalendarService
    svc = CalendarService()

    with console.status("Connecting…"):
        if not svc.connect():
            console.print("[red]Not connected.[/red] Run: topgun calendar setup")
            raise typer.Exit(1)
        svc.get_or_create_calendar()

    with console.status("Syncing…"):
        result = svc.sync()

    console.print(f"[green]synced[/green]  unchanged={result.unchanged}  modified={len(result.user_modified)}  deleted={len(result.deleted)}")
    if result.user_modified:
        for tid in result.user_modified:
            console.print(f"  [yellow]user modified:[/yellow] {tid}")


@app.command("schedule")
def schedule():
    """Compute schedule and push events to Apple Calendar."""
    from topgun.services.calendar import CalendarService
    from topgun.cli.timer_match import fetch_tasks

    svc = CalendarService()
    with console.status("Connecting…"):
        if not svc.connect():
            console.print("[red]Not connected.[/red] Run: topgun calendar setup")
            raise typer.Exit(1)
        svc.get_or_create_calendar()

    with console.status("Fetching tasks…"):
        tasks = fetch_tasks(statuses=["open"])

    task_dicts = []
    for t in tasks:
        task_dicts.append({
            "id": t["id"],
            "title": t["title"],
            "state": t.get("state", "open"),
            "due": t.get("due", ""),
            "priority": t.get("priority", ""),
            "estimated_minutes": t.get("estimated_minutes", 60),
        })

    with console.status("Scheduling…"):
        result = svc.schedule_and_push(task_dicts)

    if result.scheduled:
        console.print(f"\n[green]Scheduled {len(result.scheduled)} event(s)[/green]\n")
        for slot in result.scheduled:
            start_str = slot.start.strftime("%d-%b %H:%M")
            end_str = slot.end.strftime("%H:%M")
            console.print(f"  [cyan]{slot.task_title}[/cyan]  {start_str}–{end_str}")
    else:
        console.print("[dim]No tasks to schedule[/dim]")

    if result.unschedulable:
        console.print(f"\n[yellow]{len(result.unschedulable)} unschedulable:[/yellow]")
        for u in result.unschedulable:
            console.print(f"  [dim]{u['title']}[/dim] — {u['reason']}")
    console.print()
