from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

CLAUDE_MD = """\
# {project_name}

## Overview
[What this project does in 2–3 sentences.]

## Tech stack
[Languages, frameworks, key dependencies.]

## Common commands
```
test:   [command]
build:  [command]
lint:   [command]
```

## Project structure
[Key directories and what lives in them.]

## Conventions
[Coding conventions, naming rules, anything Claude should know.]
"""

SETTINGS_JSON = """\
{}
"""


def init(
    project_dir: Path = typer.Argument(
        Path("/project"),
        help="Project root to initialise (defaults to current directory in container)",
        show_default=False,
        hidden=True,
    ),
):
    """Scaffold a .claude/ directory inside the current project."""

    claude_dir = project_dir / ".claude"

    console.print()
    console.print(Panel("[bold magenta]rose init[/bold magenta]", expand=False))
    console.print(f"  Project: [cyan]{project_dir}[/cyan]\n")

    if claude_dir.exists():
        console.print(
            "  [yellow]Warning:[/yellow] .claude/ already exists — nothing written.\n"
            "  Remove it first if you want to reinitialise.\n"
        )
        raise typer.Exit(1)

    project_name = project_dir.resolve().name
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text(CLAUDE_MD.format(project_name=project_name))
    (claude_dir / "settings.json").write_text(SETTINGS_JSON)

    results = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    results.add_column("status", style="bold", width=4)
    results.add_column("item")

    results.add_row("[green]✓[/green]", ".claude/CLAUDE.md")
    results.add_row("[green]✓[/green]", ".claude/settings.json")

    console.print(results)
    console.print(
        "  Edit [cyan].claude/CLAUDE.md[/cyan] to add project-specific context.\n"
        "  Global persona and rules come from [cyan]~/.claude/CLAUDE.md[/cyan] automatically.\n"
    )
