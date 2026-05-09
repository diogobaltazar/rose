import typer
from typer import rich_utils as _ru

from topgun.cli.config import (
    SUPPORTED_BACKENDS,
    SUPPORTED_PROVIDERS,
    _read,
    _write,
)
from topgun.cli.theme import console, make_table, SAGE, SMOKE, PEARL, LEAF, ERR, WARN

# Apply palette: green / pearl / dark-grey
_ru.STYLE_COMMANDS_TABLE_FIRST_COLUMN = SAGE        # command names → sage green
_ru.STYLE_OPTION = SAGE                             # --flags → sage green
_ru.STYLE_SWITCH = SAGE                             # -f flags → sage green
_ru.STYLE_METAVAR = SMOKE                           # [OPTIONS] [ARGS] → dark grey
_ru.STYLE_METAVAR_SEPARATOR = SMOKE
_ru.STYLE_USAGE = SMOKE                             # "Usage:" label → dark grey
_ru.STYLE_USAGE_COMMAND = f"bold {PEARL}"           # command path → pearl bold
_ru.STYLE_HELPTEXT_FIRST_LINE = PEARL               # first help line → pearl
_ru.STYLE_HELPTEXT = PEARL                          # remaining help → pearl
_ru.STYLE_OPTION_HELP = SMOKE                       # option descriptions → dark grey
_ru.STYLE_OPTION_DEFAULT = SMOKE
_ru.STYLE_OPTIONS_PANEL_BORDER = SMOKE              # panel chrome → dark grey
_ru.STYLE_COMMANDS_PANEL_BORDER = SMOKE

app = typer.Typer(
    name="connection",
    help="Manage storage backends and service connections.",
    add_completion=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
)


@app.callback()
def _connection_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("set")
def connection_set(
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
            console.print(f"[{ERR}]Usage: topgun connection set backend <provider>[/{ERR}]")
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
            console.print(f"[{ERR}]--name required. Example: topgun connection set {key} --name my-{key}[/{ERR}]")
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
def connection_list():
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
def connection_remove(
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
