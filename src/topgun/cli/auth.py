"""CLI auth commands — topgun auth login/logout/status."""

import json
import os
import time
import webbrowser
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()
app = typer.Typer(
    name="auth",
    help="Authenticate topgun and connected services.",
    add_completion=False,
    invoke_without_command=True,
)

def _config_dir() -> Path:
    cfg = os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config" / "topgun" / "config.json"))
    return Path(cfg).parent

AUTH0_DOMAIN = ""  # loaded from API /config at runtime
AUTH0_CLIENT_ID = ""
AUTH0_AUDIENCE = ""

def _api_base() -> str:
    return os.environ.get("TOPGUN_API") or "http://localhost:5101"


def _load_auth() -> dict | None:
    f = _config_dir() / "auth.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def _save_auth(data: dict) -> None:
    f = _config_dir() / "auth.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


def _load_config() -> dict:
    f = _config_dir() / "config.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


def _access_token() -> str | None:
    auth = _load_auth()
    return auth.get("access_token") if auth else None


@app.callback()
def _auth_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("login")
def auth_login(
    name: str = typer.Option(None, "--name", help="Service connection name to authenticate"),
    backend: bool = typer.Option(False, "--backend", help="Authenticate the storage backend"),
):
    """Authenticate topgun, the storage backend, or a named service connection."""
    if name:
        _login_service(name)
    elif backend:
        _login_backend()
    else:
        _login_topgun()


def _login_topgun():
    """Auth0 device flow."""
    try:
        r = httpx.get(f"{_api_base()}/config", timeout=10)
        r.raise_for_status()
        cfg = r.json()
    except Exception as e:
        console.print(f"[red]Cannot reach topgun API: {e}[/red]")
        raise typer.Exit(1)

    domain = cfg.get("auth0_domain", "")
    client_id = cfg.get("auth0_cli_client_id") or cfg.get("auth0_client_id", "")
    audience = cfg.get("auth0_audience", "")

    if not domain or not client_id:
        console.print("[red]Auth0 not configured on this server.[/red]")
        raise typer.Exit(1)

    # Device authorization request
    device_url = f"https://{domain}/oauth/device/code"
    payload = {"client_id": client_id, "scope": "openid profile email offline_access"}
    # Only include audience in production — local dev Auth0 tenants may not
    # recognise the production API identifier
    api_base = _api_base()
    is_local = "localhost" in api_base or "127.0.0.1" in api_base
    if audience and not is_local:
        payload["audience"] = audience

    try:
        r = httpx.post(device_url, data=payload, timeout=10)
        r.raise_for_status()
        device = r.json()
    except Exception as e:
        console.print(f"[red]Device flow failed: {e}[/red]")
        raise typer.Exit(1)

    verification_uri = device.get("verification_uri_complete") or device.get("verification_uri")
    user_code = device.get("user_code", "")
    device_code = device["device_code"]
    interval = device.get("interval", 5)
    expires_in = device.get("expires_in", 300)

    console.print()
    console.print(f"[yellow]Open this URL in your browser:[/yellow]")
    console.print(f"  [bold]{verification_uri}[/bold]")
    console.print(f"[dim]  Code: {user_code}[/dim]")
    console.print()

    webbrowser.open(verification_uri)

    token_url = f"https://{domain}/oauth/token"
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        try:
            tr = httpx.post(
                token_url,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": client_id,
                },
                timeout=10,
            )
            data = tr.json()
            if tr.is_success and "access_token" in data:
                # Prefer id_token (always a JWT) over access_token
                # which may be opaque when no audience is configured
                if "id_token" in data:
                    data["access_token"] = data["id_token"]
                _save_auth(data)
                console.print("[green]Authenticated.[/green]")
                return
            err = data.get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            console.print(f"[red]Auth error: {err}[/red]")
            raise typer.Exit(1)
        except httpx.RequestError:
            continue

    console.print("[red]Timed out waiting for authorization.[/red]")
    raise typer.Exit(1)


def _login_backend():
    """Trigger Google OAuth for the storage backend via the API.
    Automatically runs Auth0 login first if not already authenticated."""
    token = _access_token()
    if not token:
        console.print("[dim]Not logged in — authenticating with topgun first...[/dim]")
        _login_topgun()
        token = _access_token()
        if not token:
            console.print("[red]Auth0 login failed.[/red]")
            raise typer.Exit(1)
        console.print()

    cfg = _load_config()
    storage = cfg.get("storage", {})
    backend = storage.get("provider", "")
    if not backend:
        console.print("[red]No backend configured. Run: topgun config set backend gdrive[/red]")
        raise typer.Exit(1)

    client_id = storage.get("client_id", "")
    client_secret = storage.get("client_secret", "")
    if not client_id or not client_secret:
        console.print("[red]Missing OAuth credentials. Run:[/red]")
        console.print(f"  topgun config set backend {backend} --client-id <id> --client-secret <secret>")
        raise typer.Exit(1)

    try:
        r = httpx.get(
            f"{_api_base()}/connect/backend/init",
            headers={"Authorization": f"Bearer {token}"},
            params={"client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        r.raise_for_status()
        auth_url = r.json().get("auth_url", "")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print(f"[yellow]Opening browser for {backend} authentication...[/yellow]")
    console.print(f"  [bold]{auth_url}[/bold]")
    console.print()
    webbrowser.open(auth_url)
    console.print("[dim]Complete the OAuth flow in your browser. The backend will receive the token automatically.[/dim]")


def _login_service(name: str):
    """Authenticate a named service connection (GitHub OAuth, etc.)."""
    cfg = _load_config()
    connections = cfg.get("connections", {})
    if name not in connections:
        console.print(f"[red]No connection named '{name}'. Run: topgun config set github --name {name}[/red]")
        raise typer.Exit(1)

    provider = connections[name].get("provider", "")
    if provider == "github":
        _login_github(name)
    else:
        console.print(f"[red]OAuth not yet implemented for provider: {provider}[/red]")
        raise typer.Exit(1)


def _login_github(name: str):
    """GitHub device flow."""
    import os
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    if not client_id:
        console.print("[red]GITHUB_CLIENT_ID env var not set.[/red]")
        raise typer.Exit(1)

    try:
        r = httpx.post(
            "https://github.com/login/device/code",
            data={"client_id": client_id, "scope": "repo"},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        device = r.json()
    except Exception as e:
        console.print(f"[red]GitHub device flow failed: {e}[/red]")
        raise typer.Exit(1)

    console.print()
    console.print(f"[yellow]Open:[/yellow] [bold]{device['verification_uri']}[/bold]")
    console.print(f"[yellow]Enter code:[/yellow] [bold]{device['user_code']}[/bold]")
    console.print()
    webbrowser.open(device["verification_uri"])

    interval = device.get("interval", 5)
    deadline = time.time() + device.get("expires_in", 300)
    while time.time() < deadline:
        time.sleep(interval)
        try:
            tr = httpx.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": client_id,
                    "device_code": device["device_code"],
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
                headers={"Accept": "application/json"},
                timeout=10,
            )
            data = tr.json()
            if "access_token" in data:
                # Store token via backend API (saved to Drive credentials.enc)
                token = _access_token()
                httpx.post(
                    f"{_api_base()}/connect/service",
                    json={"name": name, "provider": "github", "token": data["access_token"]},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                console.print(f"[green]GitHub connected as '{name}'.[/green]")
                return
            if data.get("error") == "authorization_pending":
                continue
        except Exception:
            continue

    console.print("[red]Timed out.[/red]")
    raise typer.Exit(1)


@app.command("logout")
def auth_logout(
    name: str = typer.Option(None, "--name", help="Service connection name to revoke"),
):
    """Revoke topgun authentication or a named service connection."""
    if name:
        token = _access_token()
        if not token:
            console.print("[red]Not logged in.[/red]")
            raise typer.Exit(1)
        try:
            r = httpx.delete(
                f"{_api_base()}/connect/{name}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            r.raise_for_status()
            console.print(f"[green]Connection '{name}' removed.[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
        return

    f = _config_dir() / "auth.json"
    if f.exists():
        f.unlink()
    console.print("[green]Logged out.[/green]")


@app.command("status")
def auth_status():
    """Show all authentication states."""
    auth = _load_auth()
    cfg = _load_config()

    table = Table(box=box.MINIMAL_DOUBLE_HEAD, show_edge=False)
    table.add_column("Service", style="dim")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    table.add_row(
        "topgun",
        "[green]authenticated[/green]" if auth else "[red]not logged in[/red]",
        "run: topgun auth login" if not auth else "",
    )

    backend = cfg.get("storage", {}).get("provider", "")
    table.add_row(
        f"backend ({backend or '—'})",
        "[dim]configured[/dim]" if backend else "[red]not set[/red]",
        "run: topgun config set backend gdrive" if not backend else "run: topgun auth login backend",
    )

    for name, conn in cfg.get("connections", {}).items():
        table.add_row(name, f"[dim]{conn.get('provider', '')}[/dim]", conn.get("account", ""))

    console.print()
    console.print(table)
    console.print()
