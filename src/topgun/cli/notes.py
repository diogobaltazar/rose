import json
import os
from pathlib import Path

import typer
from rich.console import Console

CONFIG_FILE = Path(
    os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config/topgun/config.json"))
)

console = Console()
app = typer.Typer(name="notes", help="Manage your notes vaults.", add_completion=False, invoke_without_command=True)


@app.callback()
def _notes_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


TYPE_COLOR = {"obsidian": "magenta"}

def _type_tag(t: str) -> str:
    color = TYPE_COLOR.get(t, "white")
    return f"[{color}]{t}[/{color}]"


def _read_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _get_sources() -> list[dict]:
    return _read_config().get("notes", {}).get("sources", [])


@app.command("track")
def track(
    path: str = typer.Option(None, "--path", help="Obsidian vault path"),
    description: str = typer.Option(None, "--description", "-d", help="Description"),
):
    """Add an Obsidian vault as a notes source."""
    data = _read_config()
    sources = data.setdefault("notes", {}).setdefault("sources", [])

    raw = path or typer.prompt("Vault path").strip()
    if raw.startswith("~"):
        resolved = raw
    else:
        _p = Path(raw)
        _parts = _p.parts
        if ".topgun" in _parts:
            _idx = _parts.index(".topgun")
            _rest = Path(*_parts[_idx + 1:]) if _idx + 1 < len(_parts) else Path(".")
            resolved = str(Path("~") / ".topgun" / _rest)
        else:
            resolved = str(_p)

    if any(s.get("path") == resolved for s in sources):
        typer.echo("already tracked")
        raise typer.Exit()

    if description is None:
        description = typer.prompt("Description", default="").strip()

    entry = {"type": "obsidian", "path": resolved, "description": description}
    sources.append(entry)
    _write_config(data)
    console.print(f"[green]ok[/green]  {_type_tag('obsidian')}\t[cyan]{resolved}[/cyan]")


@app.command("untrack")
def untrack():
    """Remove a notes vault."""
    sources = _get_sources()
    if not sources:
        typer.echo("no vaults tracked — run: topgun notes track")
        raise typer.Exit()

    for i, s in enumerate(sources, 1):
        console.print(f"  [dim]{i}[/dim]  {_type_tag(s['type'])}\t{s.get('path', '?')}")

    raw = typer.prompt("remove #")
    try:
        idx = int(raw.strip()) - 1
        assert 0 <= idx < len(sources)
    except (ValueError, AssertionError):
        typer.echo("error: invalid selection", err=True)
        raise typer.Exit(1)

    removed = sources.pop(idx)
    data = _read_config()
    data.setdefault("notes", {})["sources"] = sources
    _write_config(data)
    console.print(f"[green]ok[/green]  removed [cyan]{removed.get('path', '?')}[/cyan]")


@app.command("sources")
def sources_cmd():
    """List all tracked notes vaults."""
    sources = _get_sources()
    if not sources:
        typer.echo("no vaults tracked — run: topgun notes track")
        raise typer.Exit()

    for s in sources:
        desc = s.get("description", "")
        console.print(f"  {_type_tag(s['type'])}\t[cyan]{s.get('path', '?')}[/cyan]\t[dim]{desc}[/dim]")
