import typer
from commands.init import init
from commands.install import install
from commands.remove import remove
from commands.add import add
from commands.register import register
from commands.uninstall import uninstall

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

if __name__ == "__main__":
    app()
