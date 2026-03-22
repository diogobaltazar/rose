import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


def remove(
    target: Path = typer.Argument(
        Path("/project"),
        help="Target project directory",
        show_default=False,
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Remove rose Claude setup from a project directory."""

    console.print()
    console.print(Panel("[bold red]rose remove[/bold red]", expand=False))
    console.print(f"  Target: [cyan]{target}[/cyan]\n")

    agents_dir = target / ".claude" / "agents"
    claude_md = target / "CLAUDE.md"

    to_remove = []
    if agents_dir.exists():
        to_remove.append(agents_dir)
    if claude_md.exists():
        to_remove.append(claude_md)

    if not to_remove:
        console.print("  [dim]Nothing to remove — rose files not found.[/dim]\n")
        raise typer.Exit()

    preview = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    preview.add_column("item", style="red")
    for path in to_remove:
        preview.add_row(str(path.relative_to(target)))
    console.print(preview)

    if not yes:
        confirmed = typer.confirm("  Remove these files?", default=False)
        if not confirmed:
            console.print("\n  [dim]Aborted.[/dim]\n")
            raise typer.Exit()

    results = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    results.add_column("status", style="bold", width=4)
    results.add_column("item")

    for path in to_remove:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        results.add_row("[red]✗[/red]", str(path.relative_to(target)))

    console.print()
    console.print(results)
    console.print()
