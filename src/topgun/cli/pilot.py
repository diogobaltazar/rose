"""topgun pilot — view and manage the pilot roster."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import typer

CONFIG_FILE = Path(
    os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config/topgun/config.json"))
)

from topgun.cli.theme import console, make_table, SAGE, SMOKE, LEAF, PEARL

app = typer.Typer(
    name="pilot",
    help="View and manage pilots.",
    add_completion=False,
    invoke_without_command=True,
)

DEFAULT_PILOTS = ["maverick", "rooster", "hangman", "ice", "phoenix", "payback", "fanboy", "bob"]


@app.callback()
def _pilot_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _read_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _get_pilots() -> list[str]:
    return _read_config().get("ona", {}).get("pilots", DEFAULT_PILOTS)


def _get_default_pilot() -> str:
    return _read_config().get("ona", {}).get("default_pilot", "maverick")


def _get_engaged_envs() -> list[dict]:
    """Return ONA environments whose names match the mission-*-engage-* pattern."""
    result = subprocess.run(
        ["ona", "environment", "list", "-o", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        envs = data if isinstance(data, list) else (
            data.get("environments") or data.get("items") or []
        )
        return [
            e for e in envs
            if "mission-" in (e.get("name") or "")
            and "engage-" in (e.get("name") or "")
            and (e.get("phase") or e.get("status") or e.get("state") or "").lower() == "running"
        ]
    except (json.JSONDecodeError, TypeError):
        return []


@app.command("list")
def list_cmd(
    engaged: bool = typer.Option(False, "--engaged", help="Show only pilots currently in an engagement"),
):
    """List pilots. Use --engaged to show only those currently flying."""
    pilots = _get_pilots()
    default_pilot = _get_default_pilot()

    if engaged:
        envs = _get_engaged_envs()
        if not envs:
            console.print(f"[{SMOKE}]no pilots currently engaged[/{SMOKE}]")
            return

        table = make_table(
            ("Pilot", {"style": SAGE, "no_wrap": True}),
            ("Role", {"no_wrap": True}),
            ("Environment", {"style": SMOKE}),
        )

        for env in envs:
            name = env.get("name", "")
            env_id = env.get("id", "")[:20]
            table.add_row("maverick", f"[{PEARL}]team lead[/{PEARL}]", f"{name}  {env_id}")

        console.print(table)
        return

    table = make_table(
        ("Pilot", {"style": SAGE, "no_wrap": True}),
        ("Role", {"no_wrap": True}),
    )

    for pilot in pilots:
        role = f"[{PEARL}]team lead[/{PEARL}]" if pilot == "maverick" else "wingman"
        marker = f" [{LEAF}]✦[/{LEAF}]" if pilot == default_pilot else ""
        table.add_row(f"{pilot}{marker}", role)

    console.print(table)
    console.print(
        f"\n  [{SMOKE}]✦ your pilot ({default_pilot})[/{SMOKE}]"
    )
