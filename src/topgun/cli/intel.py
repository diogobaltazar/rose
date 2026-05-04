"""CLI for intel document management."""

import re
import typer
from rich.console import Console
from rich.table import Table
from rich import box

from topgun.sdk.client import TopgunClient

console = Console()
app = typer.Typer(
    name="intel",
    help="Manage intel documents.",
    add_completion=False,
    invoke_without_command=True,
)


@app.callback()
def _intel_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("list")
def intel_list(
    maverick: bool = typer.Option(False, "--maverick", help="Use local data instead of API"),
):
    """List all intel documents with stats."""
    client = TopgunClient()

    if maverick:
        console.print("[dim]--maverick not yet implemented for intel list[/dim]")
        raise typer.Exit(1)

    try:
        stats = client.intel_stats()
    except Exception as e:
        console.print(f"[red]Error fetching stats: {e}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print("[bold]INTEL STATS[/bold]", style="yellow")
    console.print()

    table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_edge=False)
    table.add_column("Metric", style="dim")
    table.add_column("Count", justify="right", style="yellow")

    table.add_row("Total Intel", str(stats.get("total", 0)))
    table.add_row("GitHub", str(stats.get("by_source", {}).get("github", 0)))
    table.add_row("Obsidian", str(stats.get("by_source", {}).get("obsidian", 0)))
    table.add_row("Missions", str(stats.get("missions", 0)))
    table.add_row("Drafts", str(stats.get("drafts", 0)))
    table.add_row("Ready", str(stats.get("ready", 0)))

    console.print(table)
    console.print()

    try:
        docs = client.list_intel()
    except Exception:
        return

    if docs:
        doc_table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_edge=False)
        doc_table.add_column("UID", style="dim")
        doc_table.add_column("Source", style="cyan")
        doc_table.add_column("URL", style="blue")

        for doc in docs:
            doc_table.add_row(
                doc.get("uid", ""),
                doc.get("source", ""),
                doc.get("source_url", ""),
            )

        console.print(doc_table)


@app.command("track")
def intel_track(
    target: str = typer.Argument(help="GitHub issue URL or Obsidian vault file path to track"),
    maverick: bool = typer.Option(False, "--maverick", help="Use local data instead of API"),
):
    """Register an existing GitHub issue or Obsidian file as intel."""
    client = TopgunClient()

    if maverick:
        console.print("[dim]--maverick not yet implemented for intel track[/dim]")
        raise typer.Exit(1)

    gh_match = re.match(r"https://github\.com/([^/]+/[^/]+)/issues/(\d+)", target)
    if gh_match:
        source = "github"
        source_url = target
    else:
        source = "obsidian"
        source_url = target

    try:
        doc = client.create_intel(source=source, source_url=source_url)
        console.print(f"[green]Tracked as intel:[/green] {doc.get('uid', '')}")
        console.print(f"  source: {doc.get('source', '')}")
        console.print(f"  url: {doc.get('source_url', '')}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("search")
def intel_search(
    query: str = typer.Argument(help="Search query"),
    maverick: bool = typer.Option(False, "--maverick", help="Use local data instead of API"),
):
    """Search across registered intel documents."""
    client = TopgunClient()

    if maverick:
        console.print("[dim]--maverick not yet implemented for intel search[/dim]")
        raise typer.Exit(1)

    try:
        results = client.search_intel(query)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if not results:
        console.print("[dim]No matches found.[/dim]")
        return

    table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_edge=False)
    table.add_column("UID", style="dim")
    table.add_column("Source", style="cyan")
    table.add_column("Title")

    for r in results:
        table.add_row(r.get("uid", ""), r.get("source", ""), r.get("title", ""))

    console.print(table)
