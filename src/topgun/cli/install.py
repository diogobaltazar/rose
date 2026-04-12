from pathlib import Path

import typer

from topgun.cli.upgrade import upgrade


def install(
    claude_dir: Path = typer.Argument(
        Path.home() / ".claude",
        help="Host ~/.claude directory (mounted into container)",
        show_default=False,
    ),
):
    """Alias for `topgun upgrade`."""
    upgrade(claude_dir=claude_dir)
