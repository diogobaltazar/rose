import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

GLOBAL_FILES = {
    "settings.json": False,  # (name, is_dir)
    "hooks":         True,
    "agents":        True,
    "commands":      True,
}


def uninstall(
    claude_dir: Path = typer.Argument(
        Path("/claude"),
        help="Host ~/.claude directory (mounted into container)",
        show_default=False,
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Remove rose's global Claude Code config from the host (~/.claude)."""

    console.print()
    console.print(Panel("[bold magenta]rose uninstall[/bold magenta]", expand=False))
    console.print(f"  Target: [cyan]{claude_dir}[/cyan]\n")

    if not claude_dir.exists():
        console.print(f"  [red]Error:[/red] {claude_dir} does not exist.\n")
        raise typer.Exit(1)

    items_to_remove = [name for name, _ in GLOBAL_FILES.items() if (claude_dir / name).exists()]

    if not items_to_remove:
        console.print("  Nothing to uninstall — no rose files found in target.\n")
        raise typer.Exit(0)

    console.print("  Will remove:\n")
    for name in items_to_remove:
        console.print(f"    [red]-[/red] {claude_dir / name}")
    console.print()

    if not yes:
        typer.confirm("  Proceed?", abort=True)
        console.print()

    results = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    results.add_column("status", style="bold", width=4)
    results.add_column("item")

    for name, is_dir in GLOBAL_FILES.items():
        dst = claude_dir / name

        if not dst.exists():
            continue

        if is_dir:
            shutil.rmtree(dst)
        else:
            dst.unlink()

        results.add_row("[red]✗[/red]", name)

    console.print(results)
    console.print()
