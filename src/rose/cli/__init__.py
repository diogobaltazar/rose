import typer
from pathlib import Path
from rose.cli.install import install
from rose.cli.upgrade import upgrade
from rose.cli.config import app as config_app
from rose.cli.observe import app as observe_app
from rose.cli.session import app as session_app

app = typer.Typer(
    name="rose",
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
