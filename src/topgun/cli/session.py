import os
import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="session", help="Manage Claude Code session transcripts.", add_completion=False)
console = Console()

CLAUDE_PROJECTS = Path(os.environ.get("PROJECTS_DIR", Path.home() / ".claude" / "projects"))
VAULT           = Path(os.environ.get("TOPGUN_VAULT", Path.home() / ".topgun-vault"))


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


@app.command("archive")
def archive(
    session_id: str = typer.Argument(..., help="Session UUID to archive"),
):
    """Move a session transcript from ~/.claude to ~/.topgun-vault/archive/projects/."""
    transcript, project_dir = _find_transcript(session_id)
    dest_dir = VAULT / "archive" / "projects" / project_dir.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / transcript.name
    shutil.move(str(transcript), dest)
    console.print(f"[green]Archived[/green] {transcript.name}")
    console.print(f"  [dim]{transcript}[/dim]")
    console.print(f"  → [bold]{dest}[/bold]")


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


@app.command("clone")
def clone(
    session_id: str = typer.Argument(..., help="Session UUID to clone"),
):
    """Copy a session transcript from ~/.claude to ~/.topgun-vault/clone/projects/{id}/{datetime}/."""
    transcript, _project_dir = _find_transcript(session_id)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest_dir = VAULT / "clone" / "projects" / session_id / timestamp
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / transcript.name
    shutil.copy2(str(transcript), dest)
    console.print(f"[green]Cloned[/green] {transcript.name}")
    console.print(f"  [dim]{transcript}[/dim]")
    console.print(f"  → [bold]{dest}[/bold]")
