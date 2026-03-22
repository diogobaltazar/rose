import typer
from rose.commands.install import install
from rose.commands.init import init
from rose.commands.remove import remove
from rose.commands.uninstall import uninstall
from pathlib import Path

app = typer.Typer(
    name="rose",
    help="Installs and manages Claude Code configuration.",
    add_completion=False,
    pretty_exceptions_enable=False,
)

app.command()(install)
app.command()(init)
app.command()(remove)
app.command()(uninstall)


@app.command()
def reinstall(
    claude_dir: Path = typer.Argument(
        Path("/claude"),
        help="Host ~/.claude directory (mounted into container)",
        show_default=False,
    ),
):
    """Wipe ~/.claude and reinstall global config from scratch."""
    install(claude_dir=claude_dir, force=True, reset=True)


if __name__ == "__main__":
    app()
