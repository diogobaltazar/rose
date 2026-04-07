import shutil
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(name="session", help="Manage Claude Code session transcripts.", add_completion=False)
console = Console()

CLAUDE_PROJECTS = Path("/claude/projects")
VAULT = Path("/rose-vault")


def _find_transcript(session_id: str) -> tuple[Path, Path]:
    """Return (transcript_path, project_dir) for the given session ID, or raise."""
    for project_dir in CLAUDE_PROJECTS.iterdir():
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate, project_dir
    raise typer.BadParameter(f"No transcript found for session '{session_id}' under {CLAUDE_PROJECTS}")


@app.command("archive")
def archive(
    session_id: str = typer.Argument(..., help="Session UUID to archive"),
):
    """Move a session transcript from ~/.claude to ~/.rose-vault/archive/projects/."""
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
    """Copy a session transcript from ~/.claude to ~/.rose-vault/clone/projects/{id}/{datetime}/."""
    transcript, _project_dir = _find_transcript(session_id)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    dest_dir = VAULT / "clone" / "projects" / session_id / timestamp
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / transcript.name
    shutil.copy2(str(transcript), dest)
    console.print(f"[green]Cloned[/green] {transcript.name}")
    console.print(f"  [dim]{transcript}[/dim]")
    console.print(f"  → [bold]{dest}[/bold]")
