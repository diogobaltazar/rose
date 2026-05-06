"""Shared colour palette and table factory for the topgun CLI.

Palette: shades of green + pearl/silver neutrals.
Tables: borderless, compact, no chrome.
"""

from rich.console import Console
from rich.table import Table

console = Console()

# ── Greens ────────────────────────────────────────────────────────────────────
MINT = "color(157)"          # light mint — headers, emphasis
SAGE = "color(114)"          # sage — accents, links, info
FERN = "color(71)"           # medium fern — categories, types
MOSS = "color(28)"           # dark moss — subdued green text
LEAF = "color(40)"           # vivid leaf — success markers

# ── Neutrals ──────────────────────────────────────────────────────────────────
PEARL = "color(253)"         # warm off-white — primary text
SILVER = "color(245)"        # silver — secondary text, labels
SMOKE = "color(240)"         # subtle gray — dim / tertiary

# ── Semantic ──────────────────────────────────────────────────────────────────
WARN = "color(222)"          # soft gold
ERR = "color(167)"           # muted rose


def ok(text: str = "ok") -> str:
    return f"[{LEAF}]{text}[/{LEAF}]"


def err(text: str) -> str:
    return f"[{ERR}]{text}[/{ERR}]"


def warn(text: str) -> str:
    return f"[{WARN}]{text}[/{WARN}]"


def dim(text: str) -> str:
    return f"[{SMOKE}]{text}[/{SMOKE}]"


def accent(text: str) -> str:
    return f"[{SAGE}]{text}[/{SAGE}]"


def heading(text: str) -> str:
    return f"[{MINT}]{text}[/{MINT}]"


def make_table(*columns: tuple[str, dict], show_header: bool = True) -> Table:
    """Create a borderless, compact table.

    Each column is (name, kwargs) where kwargs are passed to add_column.
    """
    t = Table(
        box=None,
        show_header=show_header,
        header_style=MINT,
        pad_edge=False,
        show_edge=False,
        padding=(0, 2, 0, 0),
    )
    for name, kw in columns:
        t.add_column(name, **kw)
    return t
