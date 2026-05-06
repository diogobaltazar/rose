import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import typer

app = typer.Typer(name="session", help="Manage Claude Code session transcripts.", add_completion=False, invoke_without_command=True)


@app.callback()
def _session_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

from topgun.cli.theme import console, make_table, SAGE, SMOKE, LEAF, ERR

_CLAUDE_DIR     = Path(os.environ.get("CLAUDE_DIR",      Path.home() / ".claude"))
_TOPGUN_DIR     = Path(os.environ.get("TOPGUN_DIR",      Path.home() / ".topgun"))
CLAUDE_PROJECTS = Path(os.environ.get("PROJECTS_DIR",    _CLAUDE_DIR / "projects"))
ARCHIVE         = Path(os.environ.get("TOPGUN_ARCHIVE",  _TOPGUN_DIR / "archive"))

# Matches a UUID v4 directory name — used to identify new-format session dirs.
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _dir_stats(path: Path) -> tuple[int, float]:
    """Return (total_size_bytes, newest_mtime) for all files under path in one pass.

    Uses os.scandir() recursively rather than Path.rglob() because scandir()
    populates DirEntry.stat() from the OS directory-listing syscall — no
    additional stat() call per entry on most filesystems. On macOS Docker bind
    mounts, where each stat() round-trip through the virtual filesystem layer
    carries measurable overhead, this halves the number of syscalls compared to
    calling _dir_size() and _dir_mtime() separately.
    """
    total_size = 0
    newest_mtime = path.stat().st_mtime
    stack = [str(path)]
    while stack:
        with os.scandir(stack.pop()) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                else:
                    st = entry.stat(follow_symlinks=False)
                    total_size += st.st_size
                    if st.st_mtime > newest_mtime:
                        newest_mtime = st.st_mtime
    return total_size, newest_mtime


def _collect_sessions() -> list[dict]:
    """
    Discover all sessions under CLAUDE_PROJECTS, supporting two storage formats:

    - Legacy: a {session_id}.jsonl file directly inside the project directory.
    - New: a UUID-named subdirectory inside the project directory (contains
      a subagents/ tree; no top-level transcript file).

    Returns a list of dicts with keys:
        session_id, project, project_dir, modified, size, format
    """
    sessions = []
    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue

        # Legacy format — top-level *.jsonl files.
        for transcript in project_dir.glob("*.jsonl"):
            stat = transcript.stat()
            sessions.append({
                "session_id": transcript.stem,
                "project": project_dir.name,
                "project_dir": project_dir,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "size": stat.st_size,
                "format": "legacy",
            })

        # New format — UUID-named subdirectories.
        for entry in project_dir.iterdir():
            if entry.is_dir() and _UUID_RE.match(entry.name):
                size, mtime = _dir_stats(entry)
                sessions.append({
                    "session_id": entry.name,
                    "project": project_dir.name,
                    "project_dir": project_dir,
                    "modified": datetime.fromtimestamp(mtime),
                    "size": size,
                    "format": "new",
                })

    return sessions


def _find_session(session_id: str) -> tuple[Path, Path, str]:
    """
    Locate a session by ID across both storage formats.

    Returns (session_path, project_dir, format) where session_path is:
    - the .jsonl file for legacy sessions
    - the UUID directory for new-format sessions
    """
    for project_dir in CLAUDE_PROJECTS.iterdir():
        if not project_dir.is_dir():
            continue
        legacy = project_dir / f"{session_id}.jsonl"
        if legacy.exists():
            return legacy, project_dir, "legacy"
        new_fmt = project_dir / session_id
        if new_fmt.is_dir() and _UUID_RE.match(session_id):
            return new_fmt, project_dir, "new"
    raise typer.BadParameter(f"No session found for '{session_id}' under {CLAUDE_PROJECTS}")


def _format_size(size_bytes: int) -> str:
    """Return a human-readable file size string (KB or MB)."""
    if size_bytes < 1_000_000:
        return f"{size_bytes / 1_000:.1f} KB"
    return f"{size_bytes / 1_000_000:.1f} MB"


@app.command("list")
def list_sessions():
    """List all sessions in ~/.claude/projects/, newest first."""
    if not CLAUDE_PROJECTS.exists():
        console.print(f"[{SMOKE}]No projects directory found at {CLAUDE_PROJECTS}[/{SMOKE}]")
        raise typer.Exit()

    sessions = _collect_sessions()

    if not sessions:
        console.print(f"[{SMOKE}]No session transcripts found.[/{SMOKE}]")
        raise typer.Exit()

    sessions.sort(key=lambda s: s["modified"], reverse=True)

    table = make_table(
        ("Session ID", {"style": SAGE, "no_wrap": True}),
        ("Project", {}),
        ("Last Modified", {"style": SMOKE}),
        ("Size", {"justify": "right"}),
    )

    for s in sessions:
        table.add_row(
            s["session_id"],
            s["project"],
            s["modified"].strftime("%Y-%m-%d %H:%M"),
            _format_size(s["size"]),
        )

    console.print(table)


def _archive_session(session: dict) -> None:
    """Move a session to the archive, handling both storage formats."""
    dest_dir = ARCHIVE / "projects" / session["project_dir"].name
    dest_dir.mkdir(parents=True, exist_ok=True)

    if session["format"] == "legacy":
        transcript = session["project_dir"] / f"{session['session_id']}.jsonl"
        shutil.move(str(transcript), dest_dir / transcript.name)
        # Move the accompanying UUID dir if it exists (pre-existing convention).
        session_dir = session["project_dir"] / session["session_id"]
        if session_dir.exists():
            shutil.move(str(session_dir), dest_dir / session["session_id"])
    else:
        session_dir = session["project_dir"] / session["session_id"]
        shutil.move(str(session_dir), dest_dir / session["session_id"])


@app.command("archive")
def archive():
    """Interactively select and archive sessions from ~/.claude to ~/.topgun/archive/."""
    import questionary
    from prompt_toolkit.formatted_text import ANSI, to_formatted_text

    if not CLAUDE_PROJECTS.exists():
        console.print(f"[dim]No projects directory found at {CLAUDE_PROJECTS}[/dim]")
        raise typer.Exit()

    sessions = _collect_sessions()

    if not sessions:
        console.print(f"[{SMOKE}]No sessions found.[/{SMOKE}]")
        raise typer.Exit()

    sessions.sort(key=lambda s: s["modified"], reverse=True)

    # Pre-calculate column widths for alignment.
    max_size = max(len(_format_size(s["size"])) for s in sessions)

    # ANSI codes — prompt_toolkit renders these natively in questionary titles.
    _DIM    = "\033[2m"
    _CYAN   = "\033[36m"
    _GREEN  = "\033[32m"
    _MAG    = "\033[35m"
    _RESET  = "\033[0m"

    choices = [
        questionary.Choice(
            title=to_formatted_text(ANSI(
                f"{_DIM}{s['modified'].strftime('%Y-%m-%d %H:%M')}{_RESET}  "
                f"{_CYAN}{s['session_id']}{_RESET}  "
                f"{_GREEN}{_format_size(s['size']).rjust(max_size)}{_RESET}  "
                f"{_MAG}{s['project']}{_RESET}"
            )),
            value=s,
        )
        for s in sessions
    ]

    selected = questionary.checkbox("Select sessions to archive:", choices=choices).ask()

    if not selected:
        console.print("[dim]nothing selected[/dim]")
        raise typer.Exit()

    for s in selected:
        _archive_session(s)
        console.print(f"[{LEAF}]archived[/{LEAF}]  {s['session_id']}")


@app.command("delete")
def delete(
    session_id: str = typer.Argument(..., help="Session UUID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Permanently delete a session from ~/.claude."""
    session_path, _project_dir, fmt = _find_session(session_id)
    if not yes:
        typer.confirm(f"Delete {session_path}?", abort=True)
    if fmt == "legacy":
        session_path.unlink()
    else:
        shutil.rmtree(session_path)
    console.print(f"[{ERR}]deleted[/{ERR}] {session_path}")
