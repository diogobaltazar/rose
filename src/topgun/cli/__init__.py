import typer
from pathlib import Path
from topgun.cli.install import install
from topgun.cli.upgrade import upgrade
from topgun.cli.config import app as config_app
from topgun.cli.observe import app as observe_app
from topgun.cli.session import app as session_app

app = typer.Typer(
    name="topgun",
    help="Installs and manages Claude Code configuration.",
    add_completion=False,
    pretty_exceptions_enable=False,
)

app.command()(install)
app.command()(upgrade)
app.add_typer(config_app)
app.add_typer(observe_app)
app.add_typer(session_app)


if __name__ == "__main__":
    app()
