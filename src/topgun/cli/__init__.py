import os
import time
import typer
from pathlib import Path
from topgun.cli.install import install
from topgun.cli.upgrade import upgrade
from topgun.cli.auth import app as auth_app
from topgun.cli.config import app as config_app
from topgun.cli.intel import app as intel_app
from topgun.cli.mission import app as mission_app
from topgun.cli.notes import app as notes_app
from topgun.cli.observe import app as observe_app
from topgun.cli.pilot import app as pilot_app
from topgun.cli.session import app as session_app
from topgun.cli.task import app as task_app
from topgun.cli.theme import console, SMOKE

app = typer.Typer(
    name="topgun",
    help="Installs and manages Claude Code configuration.",
    add_completion=False,
    pretty_exceptions_enable=False,
    invoke_without_command=True,
    rich_markup_mode=None,
)


def _warn_if_no_api_key() -> None:
    for var in ("TOPGUN_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"):
        if os.environ.get(var, "").strip():
            return
    with console.status(
        f"[{SMOKE}]no api key found — some operations unavailable  "
        f"(set TOPGUN_ANTHROPIC_API_KEY)[/{SMOKE}]",
        spinner="dots",
        spinner_style=SMOKE,
    ):
        time.sleep(1.2)


@app.callback()
def main(ctx: typer.Context):
    _warn_if_no_api_key()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.command()(install)
app.command()(upgrade)
app.add_typer(auth_app)
app.add_typer(config_app)
app.add_typer(intel_app)
app.add_typer(mission_app)
app.add_typer(notes_app)
app.add_typer(observe_app)
app.add_typer(pilot_app)
app.add_typer(session_app)
app.add_typer(task_app)


if __name__ == "__main__":
    app()
