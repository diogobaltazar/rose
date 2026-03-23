import typer
from pathlib import Path
from rose.cli.install import install
from rose.cli.uninstall import uninstall
app = typer.Typer(
    name="rose",
    help="Installs and manages Claude Code configuration.",
    add_completion=False,
    pretty_exceptions_enable=False,
)

app.command()(install)
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
