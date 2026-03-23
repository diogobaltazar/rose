import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

ROSE_DIR = Path("/rose")

GLOBAL_FILES = {
    "CLAUDE.md":     ("CLAUDE.md",     False),  # (src relative to /rose/global, is_dir)
    "settings.json": ("settings.json", False),
    "agents":        ("agents",        True),
    "commands":      ("commands",      True),
    "hooks":         ("hooks",         True),
}


def install(
    claude_dir: Path = typer.Argument(
        Path("/claude"),
        help="Host ~/.claude directory (mounted into container)",
        show_default=False,
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    reset: bool = typer.Option(False, "--reset", help="Wipe target directory before installing"),
):
    """Install global Claude Code config onto the host (~/.claude)."""

    if reset:
        if claude_dir.exists():
            shutil.rmtree(claude_dir)
        claude_dir.mkdir(parents=True, exist_ok=True)
        force = True

    console.print()
    console.print(Panel("[bold magenta]rose install[/bold magenta]", expand=False))
    console.print(f"  Target: [cyan]~/.claude[/cyan]\n")

    if not claude_dir.exists():
        console.print(f"  [red]Error:[/red] {claude_dir} does not exist.\n")
        console.print("  Make sure ~/.claude is mounted. See README for the alias.\n")
        raise typer.Exit(1)

    global_src = ROSE_DIR / "global"
    results = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    results.add_column("status", style="bold", width=4)
    results.add_column("item")
    results.add_column("note", style="dim")

    for name, (src_name, is_dir) in GLOBAL_FILES.items():
        src = global_src / src_name
        dst = claude_dir / name

        if not src.exists():
            results.add_row("[yellow]?[/yellow]", name, "not found in image, skipped")
            continue

        if dst.exists() and not force:
            results.add_row("~", name, "already exists, skipped (use --force to overwrite)")
            continue

        if dst.exists() and force:
            if is_dir:
                shutil.rmtree(dst)
            else:
                dst.unlink()

        if is_dir:
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)

        results.add_row("[green]✓[/green]", name, "installed")

    console.print(results)

    console.print()
