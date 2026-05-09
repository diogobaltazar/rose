import json
import os
from pathlib import Path

import typer

from topgun.cli.theme import console, SMOKE

CONFIG_FILE = Path(
    os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config" / "topgun" / "config.json"))
)

SUPPORTED_BACKENDS = ["gdrive", "s3"]
SUPPORTED_PROVIDERS = ["github", "caldav", "gdrive"]

app = typer.Typer(
    name="config",
    help="Manage topgun configuration.",
    add_completion=False,
    invoke_without_command=True,
    rich_markup_mode=None,
)
observe_app = typer.Typer(
    name="observe",
    help="Projects to monitor with topgun observe.",
    add_completion=False,
    invoke_without_command=True,
    rich_markup_mode=None,
)
app.add_typer(observe_app)


@app.callback()
def _config_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@observe_app.callback()
def _observe_config_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _read() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


@observe_app.command("add")
def observe_add(path: str = typer.Argument(..., help="Absolute path to the project root")):
    """Register a project for topgun observe to monitor."""
    resolved = str(Path(path).resolve())
    data = _read()
    projects = data.setdefault("projects", [])
    if resolved in projects:
        typer.echo(f"Already registered: {resolved}")
        raise typer.Exit()
    projects.append(resolved)
    _write(data)
    typer.echo(f"Added: {resolved}")


@observe_app.command("remove")
def observe_remove(path: str = typer.Argument(..., help="Path to deregister")):
    """Deregister a project from topgun observe."""
    resolved = str(Path(path).resolve())
    data = _read()
    projects = data.get("projects", [])
    if resolved not in projects:
        typer.echo(f"Not registered: {resolved}")
        raise typer.Exit()
    projects.remove(resolved)
    data["projects"] = projects
    _write(data)
    typer.echo(f"Removed: {resolved}")


@observe_app.command("list")
def observe_list():
    """List registered projects."""
    projects = _read().get("projects", [])
    if projects:
        for p in projects:
            typer.echo(p)
    else:
        typer.echo("No projects registered. Use: topgun config observe add <path>")
