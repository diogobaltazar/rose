import typer
from commands.init import init
from commands.install import install
from commands.remove import remove
from commands.add import add
from commands.register import register
from commands.uninstall import uninstall
from pathlib import Path

app = typer.Typer(
    name="rose",
    help="Coding agent scaffolding tool. Bootstraps Claude Code super-agent config into any project.",
    add_completion=False,
    pretty_exceptions_enable=False,
)

app.command()(install)
app.command()(init)
app.command()(remove)
app.command()(add)
app.command()(register)
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
