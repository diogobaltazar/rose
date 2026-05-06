import json
import os
from pathlib import Path

import typer

from topgun.cli.theme import console, make_table, SAGE, SMOKE, LEAF, ERR, WARN

CONFIG_FILE = Path(
    os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config" / "topgun" / "config.json"))
)

SUPPORTED_BACKENDS = ["gdrive", "s3"]
SUPPORTED_PROVIDERS = ["github", "caldav", "gdrive"]

app = typer.Typer(name="config", help="Manage topgun configuration.", add_completion=False, invoke_without_command=True)
observe_app = typer.Typer(name="observe", help="Projects to monitor with topgun observe.", add_completion=False, invoke_without_command=True)
app.add_typer(observe_app)


@app.callback()
def _config_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("set")
def config_set(
    key: str = typer.Argument(help="What to set: 'backend' or a provider (github, caldav)"),
    value: str = typer.Argument(None, help="Value for 'backend' (e.g. gdrive, s3)"),
    name: str = typer.Option(None, "--name", help="Connection name (required for services)"),
    account: str = typer.Option(None, "--account", help="Account email for this connection"),
    repos: str = typer.Option(None, "--repos", help="Comma-separated repos (github only)"),
    vault: str = typer.Option(None, "--vault", help="Vault path relative to topgun/ folder"),
    client_id: str = typer.Option(None, "--client-id", help="OAuth2 client ID (backend only)"),
    client_secret: str = typer.Option(None, "--client-secret", help="OAuth2 client secret (backend only)"),
):
    """Declare a storage backend or service connection."""
    data = _read()

    if key == "backend":
        if not value or value not in SUPPORTED_BACKENDS:
            console.print(f"[{ERR}]Usage: topgun config set backend <provider>[/{ERR}]")
            console.print(f"[{SMOKE}]Supported: {', '.join(SUPPORTED_BACKENDS)}[/{SMOKE}]")
            raise typer.Exit(1)
        storage = data.setdefault("storage", {})
        storage["provider"] = value
        if vault:
            storage["vault"] = vault
        if client_id:
            storage["client_id"] = client_id
        if client_secret:
            storage["client_secret"] = client_secret
        _write(data)
        console.print(f"[{LEAF}]Storage backend set to: {value}[/{LEAF}]")
        if not client_id or not client_secret:
            console.print(f"[{WARN}]Tip: provide --client-id and --client-secret from your GCP OAuth app[/{WARN}]")
        return

    if key in SUPPORTED_PROVIDERS:
        if not name:
            console.print(f"[{ERR}]--name required. Example: topgun config set {key} --name my-{key}[/{ERR}]")
            raise typer.Exit(1)
        conn: dict = {"provider": key}
        if account:
            conn["account"] = account
        if repos:
            conn["repos"] = [r.strip() for r in repos.split(",") if r.strip()]
        connections = data.setdefault("connections", {})
        connections[name] = conn
        _write(data)
        console.print(f"[{LEAF}]Connection '{name}' declared ({key}).[/{LEAF}]")
        if key != "caldav":
            console.print(f"[{SMOKE}]Next: topgun auth login --name {name}[/{SMOKE}]")
        return

    console.print(f"[{ERR}]Unknown: {key}[/{ERR}]")
    console.print(f"[{SMOKE}]Backends: {', '.join(SUPPORTED_BACKENDS)}  Providers: {', '.join(SUPPORTED_PROVIDERS)}[/{SMOKE}]")
    raise typer.Exit(1)


@app.command("list")
def config_list():
    """List all declared connections and storage backend."""
    data = _read()

    table = make_table(
        ("Name", {"style": SAGE}),
        ("Type", {"style": SMOKE}),
        ("Detail", {"style": SMOKE}),
    )

    backend = data.get("storage", {}).get("provider", "")
    table.add_row("backend", backend or f"[{SMOKE}]not set[/{SMOKE}]", "")

    for name, conn in data.get("connections", {}).items():
        table.add_row(name, conn.get("provider", ""), conn.get("account", ""))

    console.print(table)


@app.command("remove")
def config_remove(
    name: str = typer.Option(..., "--name", help="Connection name to remove"),
):
    """Remove a declared connection."""
    data = _read()
    connections = data.get("connections", {})
    if name not in connections:
        console.print(f"[{ERR}]No connection named '{name}'.[/{ERR}]")
        raise typer.Exit(1)
    del connections[name]
    data["connections"] = connections
    _write(data)
    console.print(f"[{LEAF}]Removed '{name}'.[/{LEAF}]")


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
