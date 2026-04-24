import typer
from pathlib import Path
from topgun.cli.install import install
from topgun.cli.upgrade import upgrade
from topgun.cli.backlog import app as backlog_app
from topgun.cli.config import app as config_app
from topgun.cli.observe import app as observe_app
from topgun.cli.session import app as session_app
from topgun.cli.backlog import app as backlog_app

app = typer.Typer(
    name="topgun",
    help="Installs and manages Claude Code configuration.",
    add_completion=False,
    pretty_exceptions_enable=False,
    invoke_without_command=True,
)


@app.callback()
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.command()(install)
app.command()(upgrade)
app.add_typer(backlog_app)
app.add_typer(config_app)
app.add_typer(observe_app)
app.add_typer(session_app)
app.add_typer(backlog_app)


if __name__ == "__main__":
    app()
