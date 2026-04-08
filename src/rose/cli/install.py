from pathlib import Path

import typer

from rose.cli.upgrade import upgrade


def install(
    claude_dir: Path = typer.Argument(
        Path("/claude"),
        help="Host ~/.claude directory (mounted into container)",
        show_default=False,
    ),
):
    """Alias for `rose upgrade`."""
    upgrade(claude_dir=claude_dir)
