import os
import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="session", help="Manage Claude Code session transcripts.", add_completion=False, invoke_without_command=True)


@app.callback()
def _session_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
console = Console()

_CLAUDE_DIR     = Path(os.environ.get("CLAUDE_DIR",      Path.home() / ".claude"))
_TOPGUN_DIR     = Path(os.environ.get("TOPGUN_DIR",      Path.home() / ".topgun"))
CLAUDE_PROJECTS = Path(os.environ.get("PROJECTS_DIR",    _CLAUDE_DIR / "projects"))
ARCHIVE         = Path(os.environ.get("TOPGUN_ARCHIVE",  _TOPGUN_DIR / "archive"))


def _find_transcript(session_id: str) -> tuple[Path, Path]:
    """Return (transcript_path, project_dir) for the given session ID, or raise."""
    for project_dir in CLAUDE_PROJECTS.iterdir():
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate, project_dir
    raise typer.BadParameter(f"No transcript found for session '{session_id}' under {CLAUDE_PROJECTS}")


def _format_size(size_bytes: int) -> str:
    """Return a human-readable file size string (KB or MB)."""
    if size_bytes < 1_000_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes / 1_000_000:.1f} MB"


@app.command("list")
def list_sessions():
    """List all session transcripts in ~/.claude/projects/, newest first."""
    if not CLAUDE_PROJECTS.exists():
        console.print(f"[dim]No projects directory found at {CLAUDE_PROJECTS}[/dim]")
        raise typer.Exit()

    sessions = []
    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue
        for transcript in project_dir.glob("*.jsonl"):
            stat = transcript.stat()
            sessions.append({
                "session_id": transcript.stem,
                "project": project_dir.name,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
            })

    if not sessions:
        console.print("[dim]No session transcripts found.[/dim]")
        raise typer.Exit()

    sessions.sort(key=lambda s: s["modified"], reverse=True)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Session ID", style="cyan", no_wrap=True)
    table.add_column("Project")
    table.add_column("Last Modified", style="dim")
    table.add_column("Size", justify="right")

    for s in sessions:
        table.add_row(
            s["session_id"],
            s["project"],
            s["modified"].strftime("%Y-%m-%d %H:%M"),
            _format_size(s["size"]),
        )

    console.print(table)


def _archive_session(session_id: str, project_dir: Path) -> None:
    """Move a single session's transcript and uuid/ directory to the archive."""
    transcript = project_dir / f"{session_id}.jsonl"
    dest_dir = ARCHIVE / "projects" / project_dir.name
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_transcript = dest_dir / transcript.name
    shutil.move(str(transcript), dest_transcript)

    session_dir = project_dir / session_id
    if session_dir.exists():
        shutil.move(str(session_dir), dest_dir / session_id)


@app.command("archive")
def archive():
    """Interactively select and archive sessions from ~/.claude to ~/.topgun/archive/."""
    import questionary

    if not CLAUDE_PROJECTS.exists():
        console.print(f"[dim]No projects directory found at {CLAUDE_PROJECTS}[/dim]")
        raise typer.Exit()

    sessions = []
    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue
        for transcript in project_dir.glob("*.jsonl"):
            stat = transcript.stat()
            sessions.append({
                "session_id": transcript.stem,
                "project": project_dir.name,
                "project_dir": project_dir,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
            })

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        raise typer.Exit()

    sessions.sort(key=lambda s: s["modified"], reverse=True)

    choices = [
        questionary.Choice(
            title=f"{s['modified'].strftime('%Y-%m-%d %H:%M')}  "
                  f"{s['session_id']}  "
                  f"[{_format_size(s['size'])}]  "
                  f"{s['project']}",
            value=s,
        )
        for s in sessions
    ]

    selected = questionary.checkbox("Select sessions to archive:", choices=choices).ask()

    if not selected:
        console.print("[dim]nothing selected[/dim]")
        raise typer.Exit()

    for s in selected:
        _archive_session(s["session_id"], s["project_dir"])
        console.print(f"[green]archived[/green]  {s['session_id']}")


@app.command("delete")
def delete(
    session_id: str = typer.Argument(..., help="Session UUID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Permanently delete a session transcript from ~/.claude."""
    transcript, _project_dir = _find_transcript(session_id)
    if not yes:
        typer.confirm(f"Delete {transcript}?", abort=True)
    transcript.unlink()
    console.print(f"[red]Deleted[/red] {transcript}")
