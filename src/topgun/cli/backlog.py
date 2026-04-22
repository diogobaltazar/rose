"""
topgun backlog — live terminal view of the federated backlog.

Commands:
  topgun backlog watch    # live Rich table, queries all configured sources
"""

import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer(name="backlog", help="Backlog inspector.", add_completion=False)

CONFIG_FILE = Path.home() / ".config" / "topgun" / "config.json"

_PRIORITY_EMOJIS = {"⏫": "high", "🔼": "medium", "🔽": "low"}
_TASK_RE = re.compile(r"^- \[([ x])\] (.+)$")
_DUE_RE = re.compile(r"📅 (\d{4}-\d{2}-\d{2})")
_SCHED_RE = re.compile(r"⏳ (\d{4}-\d{2}-\d{2})")
_DONE_RE = re.compile(r"✅ (\d{4}-\d{2}-\d{2})")


# ── Config ────────────────────────────────────────────────────────────────────


def _backlog_sources() -> list[dict]:
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
        return cfg.get("backlog", {}).get("sources", [])
    except (OSError, json.JSONDecodeError):
        return []


# ── GitHub ────────────────────────────────────────────────────────────────────


def _parse_body_section(body: str, section: str) -> str:
    pattern = rf"## {re.escape(section)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, body or "", re.DOTALL)
    return m.group(1).strip() if m else ""


def _fetch_github(source: dict) -> list[dict]:
    repo = source["repo"]
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--repo", repo,
                "--state", "all",
                "--limit", "200",
                "--json", "number,title,state,createdAt,closedAt,labels,body,url",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            return []
        issues = json.loads(result.stdout)
    except Exception:
        return []

    items = []
    for issue in issues:
        body = issue.get("body") or ""
        labels = {lbl["name"] for lbl in (issue.get("labels") or [])}
        priority = next(
            (v for k, v in {"priority:high": "high", "priority:medium": "medium", "priority:low": "low"}.items() if k in labels),
            None,
        )
        items.append({
            "source_type": "github",
            "source": repo,
            "source_description": source.get("description", ""),
            "number": issue["number"],
            "title": issue.get("title", ""),
            "state": issue.get("state", "open").lower(),
            "created_at": (issue.get("createdAt") or "")[:10],
            "closed_at": (issue.get("closedAt") or "")[:10] or None,
            "priority": priority,
            "must_before": _parse_body_section(body, "Must Before") or None,
            "best_before": _parse_body_section(body, "Best Before") or None,
            "url": issue.get("url"),
        })
    return items


# ── Obsidian ──────────────────────────────────────────────────────────────────


def _fetch_obsidian(source: dict) -> list[dict]:
    path_str = source.get("path", "")
    vault = Path(path_str.replace("~", str(Path.home()), 1)) if path_str.startswith("~") else Path(path_str)
    if not vault.exists():
        return []

    items = []
    for md_file in vault.rglob("*.md"):
        try:
            lines = md_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            m = _TASK_RE.match(line.strip())
            if not m:
                continue
            state_char, rest = m.group(1), m.group(2)
            state = "closed" if state_char == "x" else "open"
            priority = next((v for emoji, v in _PRIORITY_EMOJIS.items() if emoji in rest), None)
            must_m = _DUE_RE.search(rest)
            sched_m = _SCHED_RE.search(rest)
            done_m = _DONE_RE.search(rest)

            title = rest
            for pat in (_DUE_RE, _SCHED_RE, _DONE_RE):
                title = pat.sub("", title)
            for emoji in list(_PRIORITY_EMOJIS) + ["🔁"]:
                title = title.replace(emoji, "")
            title = title.strip()

            items.append({
                "source_type": "obsidian",
                "source": str(md_file.relative_to(vault)),
                "source_description": source.get("description", ""),
                "number": None,
                "title": title,
                "state": state,
                "created_at": None,
                "closed_at": done_m.group(1) if done_m else None,
                "priority": priority,
                "must_before": must_m.group(1) if must_m else None,
                "best_before": sched_m.group(1) if sched_m else None,
                "url": None,
            })
    return items


# ── Rendering ─────────────────────────────────────────────────────────────────


def _age(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        d = (date.today() - date.fromisoformat(iso[:10])).days
        if d == 0:
            return "today"
        if d < 30:
            return f"{d}d"
        return f"{d // 30}mo"
    except ValueError:
        return "—"


def _priority_style(p: str | None) -> str:
    return {"high": "color(216)", "medium": "color(114)", "low": "color(145)"}.get(p or "", "dim")


def _is_overdue(item: dict) -> bool:
    if item["state"] != "open":
        return False
    d = item.get("must_before") or item.get("best_before")
    if not d:
        return False
    try:
        return date.fromisoformat(d) < date.today()
    except ValueError:
        return False


def _render(items: list[dict]) -> Table:
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        padding=(0, 1),
        pad_edge=False,
        expand=True,
    )
    table.add_column("st", width=2, justify="center")
    table.add_column("title", ratio=4)
    table.add_column("source", ratio=2, style="dim")
    table.add_column("pri", width=6, justify="center")
    table.add_column("due", width=11, justify="center")
    table.add_column("sched", width=11, justify="center")
    table.add_column("age", width=6, justify="right", style="dim")

    open_items = [i for i in items if i["state"] == "open"]
    open_items.sort(key=lambda x: (
        {"high": 0, "medium": 1, "low": 2}.get(x.get("priority") or "", 3),
        x.get("must_before") or "zzzz",
    ))

    for item in open_items:
        od = _is_overdue(item)
        pri_s = _priority_style(item.get("priority"))
        pri_label = {"high": "⏫ hi", "medium": "🔼 md", "low": "🔽 lo"}.get(item.get("priority") or "", "—")
        due = item.get("must_before") or "—"
        sched = item.get("best_before") or "—"
        title = item["title"]
        if len(title) > 60:
            title = title[:57] + "…"

        table.add_row(
            "[color(118)]○[/]",
            f"[bold color(253)]{title}[/]" if od else f"[color(253)]{title}[/]",
            item["source"],
            f"[{pri_s}]{pri_label}[/]",
            f"[bold color(216)]{due}[/]" if od and due != "—" else f"[dim]{due}[/]",
            f"[dim]{sched}[/]",
            _age(item.get("created_at")),
        )

    return table


# ── Command ───────────────────────────────────────────────────────────────────


@app.command("watch")
def watch_cmd():
    """Live terminal table of all open backlog items across configured sources."""
    console = Console()
    sources = _backlog_sources()

    if not sources:
        console.print(
            "[yellow]No backlog sources configured.[/yellow]\n"
            f"Add sources to [cyan]{CONFIG_FILE}[/cyan] under [bold]backlog.sources[/bold]."
        )
        raise typer.Exit(1)

    if not sys.stdin.isatty():
        # Non-interactive: render once and exit
        items: list[dict] = []
        for s in sources:
            if s.get("type") == "github":
                items.extend(_fetch_github(s))
            elif s.get("type") == "obsidian":
                items.extend(_fetch_obsidian(s))
        console.print(_render(items))
        return

    import select
    import termios
    import tty
    import threading
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    items: list[dict] = []
    dirty = threading.Event()
    lock = threading.Lock()

    def _refresh():
        nonlocal items
        fetched: list[dict] = []
        for s in sources:
            if s.get("type") == "github":
                fetched.extend(_fetch_github(s))
            elif s.get("type") == "obsidian":
                fetched.extend(_fetch_obsidian(s))
        with lock:
            items = fetched
        dirty.set()

    # Initial fetch
    _refresh()

    # Watch Obsidian vaults for file changes
    observer = Observer()
    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if not event.is_directory and event.src_path.endswith(".md"):
                dirty.set()

    for s in sources:
        if s.get("type") == "obsidian":
            vault = Path(s["path"].replace("~", str(Path.home()), 1))
            if vault.exists():
                observer.schedule(Handler(), str(vault), recursive=True)
    observer.start()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        sys.stdout.write("\033[?1049h\033[?25l")
        sys.stdout.flush()
        tty.setcbreak(fd)

        while True:
            if dirty.is_set():
                dirty.clear()
                sys.stdout.write("\033[H\033[2J")
                sys.stdout.flush()
                with lock:
                    snapshot = list(items)
                open_count = sum(1 for i in snapshot if i["state"] == "open")
                console.print(f"\n  [bold color(118)]backlog[/]  [dim]{open_count} open[/]  [dim]q quit[/]\n")
                console.print(_render(snapshot))

            if select.select([sys.stdin], [], [], 0.5)[0]:
                ch = sys.stdin.read(1)
                if ch in ("q", "\x03"):
                    break
                elif ch == "r":
                    threading.Thread(target=_refresh, daemon=True).start()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()
        observer.stop()
        observer.join()
