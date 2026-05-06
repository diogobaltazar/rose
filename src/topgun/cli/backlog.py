import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import typer

CONFIG_FILE = Path(
    os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config/topgun/config.json"))
)

from topgun.cli.theme import console, make_table, SAGE, SMOKE, LEAF, WARN, ERR, FERN

app = typer.Typer(name="backlog", help="Manage your federated backlog.", add_completion=False, invoke_without_command=True, rich_markup_mode=None)


@app.callback()
def _backlog_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "": 3}
PRIORITY_COLOR = {"high": "red", "medium": "yellow", "low": "green"}
PRIORITY_ICON = {"⏫": "high", "🔼": "medium", "🔽": "low"}

_DUE_RE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
_PRI_RE = re.compile(r"(⏫|🔼|🔽)")
_TASK_RE = re.compile(r"^\s*- \[ \]\s*")
_TAG_RE = re.compile(r"(?<!\w)#([\w/-]+)")
_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _parse_body_section(body: str | None, section: str) -> str:
    """Return trimmed text under a '## Section' heading in a GitHub issue body."""
    if not body:
        return ""
    parts = _SECTION_RE.split(body)
    # parts: ["preamble", "Heading1", "content1", "Heading2", "content2", ...]
    for i in range(1, len(parts) - 1, 2):
        if parts[i].strip() == section:
            return parts[i + 1].strip()
    return ""


def _is_overdue(item: dict) -> bool:
    """Return True if the item is open and past its must_before (or best_before) date."""
    if item.get("state") != "open":
        return False
    today = datetime.now(timezone.utc).date().isoformat()
    date = item.get("must_before") or item.get("best_before")
    return bool(date and date < today)


def _read_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _get_sources() -> list[dict]:
    return _read_config().get("backlog", {}).get("sources", [])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TYPE_COLOR = {"github": FERN, "obsidian": FERN}

def _type_tag(t: str) -> str:
    return f"[{FERN}]{t}[/{FERN}]"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("track")
def track(
    type: str = typer.Option(None, "--type", "-t", help="github or obsidian"),
    repo: str = typer.Option(None, "--repo", help="GitHub repo (owner/repo)"),
    path: str = typer.Option(None, "--path", help="Obsidian vault path"),
    description: str = typer.Option(None, "--description", "-d", help="Description"),
    token_env: str = typer.Option(None, "--token-env", help="Token env var (github only)"),
):
    """Add a new backlog source (GitHub repo or Obsidian vault)."""
    data = _read_config()
    sources = data.setdefault("backlog", {}).setdefault("sources", [])

    if type is None:
        typer.echo("source type: [1] github  [2] obsidian")
        choice = typer.prompt("type", default="1")
        type = "github" if choice == "1" else "obsidian" if choice == "2" else None
        if type is None:
            typer.echo("error: invalid choice", err=True)
            raise typer.Exit(1)

    if type == "github":
        repo = repo or typer.prompt("GitHub repo (owner/repo)").strip()
        token_env = token_env or typer.prompt("Token env var", default="GITHUB_TOKEN").strip()
        if description is None:
            description = typer.prompt("Description", default="").strip() or _fetch_github_description(repo, token_env)
        entry = {"type": "github", "repo": repo, "description": description, "token_env": token_env}
        duplicate = any(s.get("type") == "github" and s.get("repo") == repo for s in sources)
    elif type == "obsidian":
        raw = path or typer.prompt("Vault path").strip()
        resolved = str(Path(raw).expanduser().resolve())
        if description is None:
            description = typer.prompt("Description", default="").strip()
        entry = {"type": "obsidian", "path": resolved, "description": description}
        duplicate = any(s.get("type") == "obsidian" and s.get("path") == resolved for s in sources)
    else:
        typer.echo("error: type must be github or obsidian", err=True)
        raise typer.Exit(1)

    if duplicate:
        typer.echo("already tracked")
        raise typer.Exit()

    sources.append(entry)
    _write_config(data)
    label = entry.get("repo") or entry.get("path")
    console.print(f"[{LEAF}]ok[/{LEAF}]  {_type_tag(entry['type'])}  [{SAGE}]{label}[/{SAGE}]")
    if entry["type"] == "github" and not os.environ.get(entry["token_env"]):
        console.print(f"[{WARN}]add to ~/.zshrc:[/{WARN}]  export {entry['token_env']}=$(gh auth token)")


@app.command("untrack")
def untrack():
    """Remove a backlog source."""
    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun backlog track")
        raise typer.Exit()

    for i, s in enumerate(sources, 1):
        label = s.get("repo") or s.get("path", "?")
        console.print(f"  [{SMOKE}]{i}[/{SMOKE}]  {_type_tag(s['type'])}  {label}")

    raw = typer.prompt("remove #")
    try:
        idx = int(raw.strip()) - 1
        assert 0 <= idx < len(sources)
    except (ValueError, AssertionError):
        typer.echo("error: invalid selection", err=True)
        raise typer.Exit(1)

    removed = sources.pop(idx)
    data = _read_config()
    data.setdefault("backlog", {})["sources"] = sources
    _write_config(data)
    label = removed.get("repo") or removed.get("path", "?")
    console.print(f"[{LEAF}]ok[/{LEAF}]  removed [{SAGE}]{label}[/{SAGE}]")


@app.command("sources")
def sources_cmd():
    """List all tracked backlog sources."""
    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun backlog track")
        raise typer.Exit()

    for s in sources:
        label = s.get("repo") or s.get("path", "?")
        desc = s.get("description", "")
        console.print(f"  {_type_tag(s['type'])}  [{SAGE}]{label}[/{SAGE}]  [{SMOKE}]{desc}[/{SMOKE}]")


@app.command("list")
def list_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show source path column"),
):
    """Print all open backlog items across sources."""
    sources = _get_sources()
    if not sources:
        typer.echo("no sources tracked — run: topgun backlog track")
        raise typer.Exit()

    items, errors = _fetch_all(sources)

    table = make_table(
        ("Type", {"no_wrap": True}),
        ("Title", {}),
        ("Tags", {"style": SMOKE}),
        ("Priority", {"width": 8}),
        ("Due", {"width": 12}),
        ("Status", {"width": 8}),
    )
    if verbose:
        table.add_column("Source", style=SMOKE)

    for item in sorted(items, key=_sort_key):
        pri = item["priority"]
        color = PRIORITY_COLOR.get(pri, "dim")
        status = item.get("state", "open")
        tags = "  ".join(f"#{t}" for t in item.get("tags", []))
        row = [
            _type_tag(item["type"]),
            item["title"],
            tags,
            f"[{color}]{pri}[/{color}]" if pri else "",
            item["due"],
            status,
        ]
        if verbose:
            row.append(item["source_full"])
        table.add_row(*row)

    console.print(table)
    if errors:
        for e in errors:
            console.print(f"[{WARN}]{e}[/{WARN}]")


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _fetch_all(sources: list[dict], statuses: list[str] | None = None) -> tuple[list[dict], list[str]]:
    if statuses is None:
        statuses = ["open"]
    items, errors = [], []
    for s in sources:
        if s["type"] == "github":
            fetched, err = _fetch_github(s["repo"], s.get("token_env", "GITHUB_TOKEN"), statuses=statuses)
            items.extend(fetched)
            if err:
                errors.append(err)
        elif s["type"] == "obsidian":
            items.extend(_fetch_obsidian(s["path"], statuses=statuses))
    return items, errors


def _fetch_github_description(repo: str, token_env: str) -> str:
    token = os.environ.get(token_env, "")
    env = {**os.environ, "GITHUB_TOKEN": token} if token else os.environ
    result = subprocess.run(
        ["gh", "repo", "view", repo, "--json", "description", "--jq", ".description"],
        capture_output=True, text=True, env=env,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _fetch_github(repo: str, token_env: str, statuses: list[str] | None = None) -> tuple[list[dict], str]:
    if statuses is None:
        statuses = ["open"]
    token = os.environ.get(token_env, "")
    if not token:
        return [], f"{repo}: {token_env} not set — run: export {token_env}=$(gh auth token)"

    # GitHub only understands "open", "closed", "all".
    # "inprogress" is an Obsidian-only concept; map it to "open" for GitHub.
    gh_statuses = {s for s in statuses if s in ("open", "closed")}
    if not gh_statuses:
        return [], ""
    if "open" in gh_statuses and "closed" in gh_statuses:
        gh_state = "all"
    elif "closed" in gh_statuses:
        gh_state = "closed"
    else:
        gh_state = "open"

    env = {**os.environ, "GITHUB_TOKEN": token}
    result = subprocess.run(
        [
            "gh", "issue", "list",
            "--repo", repo,
            "--state", gh_state,
            "--json", "number,title,labels,createdAt,body,state",
            "--limit", "200",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        err = result.stderr.strip().splitlines()[0] if result.stderr.strip() else "gh failed"
        if "401" in err or "auth" in err.lower():
            return [], f"{repo}: token invalid or expired — run: gh auth refresh"
        return [], f"{repo}: {err}"

    items = []
    for issue in json.loads(result.stdout or "[]"):
        issue_state = (issue.get("state") or "OPEN").upper()
        # Normalise GitHub state strings to lowercase "open"/"closed".
        state = "closed" if issue_state == "CLOSED" else "open"
        priority = ""
        tags = []
        for label in issue.get("labels", []):
            name = label.get("name", "")
            lower = name.lower()
            if "high" in lower:
                priority = "high"
            elif "medium" in lower:
                priority = "medium"
            elif "low" in lower:
                priority = "low"
            elif not lower.startswith("priority"):
                tags.append(name)
        body = issue.get("body") or ""
        must_before = _parse_body_section(body, "Must Before") or None
        best_before = _parse_body_section(body, "Best Before") or None
        items.append({
            "type": "github",
            "title": f"#{issue['number']} {issue['title']}",
            "source_full": repo,
            "priority": priority,
            "due": must_before or best_before or "",
            "state": state,
            "must_before": must_before,
            "best_before": best_before,
            "tags": tags,
            "url": f"https://github.com/{repo}/issues/{issue['number']}",
        })
    return items, ""


def _resolve_vault_path(vault_path: str) -> Path:
    """Remap host ~/.topgun paths to /topgun-data/... when running inside Docker."""
    path = Path(vault_path).expanduser()
    if path.exists():
        return path
    obsidian_dir = os.environ.get("OBSIDIAN_DIR", "")
    if obsidian_dir:
        parts = path.parts
        if ".topgun" in parts:
            idx = parts.index(".topgun")
            relative = Path(*parts[idx + 1:]) if idx + 1 < len(parts) else Path(".")
        else:
            relative = Path(path.name)
        candidate = Path(obsidian_dir) / relative
        if candidate.exists():
            return candidate
    return path


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_FM_FIELD_RE = re.compile(r"^(\w+):\s*(.*)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> dict:
    """Extract key-value pairs from YAML frontmatter (simple scalar values only)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    return {k: v.strip().strip('"').strip("'") for k, v in _FM_FIELD_RE.findall(m.group(1))}


def _fetch_obsidian(vault_path: str, statuses: list[str] | None = None) -> list[dict]:
    from urllib.parse import quote
    if statuses is None:
        statuses = ["open"]
    vault = _resolve_vault_path(vault_path)
    if not vault.exists():
        return []

    # host_vault is the path Obsidian on the host OS knows about.
    # Inside Docker, vault may be remapped (e.g. /topgun-data/...), so we
    # reconstruct the host path from the original vault_path in config.
    host_vault = Path(vault_path).expanduser()
    items = []
    for md_file in vault.rglob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        relative = md_file.relative_to(vault)
        host_file = host_vault / relative
        # Directory-based task files (slug/task.md) are opened directly in Obsidian.
        # Checkboxes in ordinary notes fall back to search so the exact line
        # is surfaced in context.
        is_task_file = relative.name == "task.md"

        # For directory-based task files, read status and due dates from
        # frontmatter and section headings rather than checkbox emoji patterns.
        if is_task_file:
            fm = _parse_frontmatter(text)
            status = fm.get("status", "open")
            if status not in statuses:
                continue
            # Due date: prefer Must Before, fall back to Best Before.
            # Strip null placeholders first so the `or` chain works correctly.
            _null = {"_none_", "none", ""}
            must_before = _parse_body_section(text, "Must Before").strip()
            must_before = must_before if must_before.lower() not in _null else ""
            best_before = _parse_body_section(text, "Best Before").strip()
            best_before = best_before if best_before.lower() not in _null else ""
            due = must_before or best_before

        for line in text.splitlines():
            if not _TASK_RE.match(line):
                continue
            title = _TASK_RE.sub("", line).strip()

            if is_task_file:
                # Due date and priority already resolved from frontmatter/sections.
                title = _DUE_RE.sub("", title).strip()
                pri_match = _PRI_RE.search(title)
                priority = PRIORITY_ICON.get(pri_match.group(1), "") if pri_match else fm.get("priority", "")
                title = _PRI_RE.sub("", title).strip()
                tags = _TAG_RE.findall(title)
                title = _TAG_RE.sub("", title).strip()
                obs_url = f"obsidian://open?path={quote(str(host_file))}"
            else:
                due_match = _DUE_RE.search(title)
                due = due_match.group(1) if due_match else ""
                title = _DUE_RE.sub("", title).strip()

                pri_match = _PRI_RE.search(title)
                priority = PRIORITY_ICON.get(pri_match.group(1), "") if pri_match else ""
                title = _PRI_RE.sub("", title).strip()

                tags = _TAG_RE.findall(title)
                title = _TAG_RE.sub("", title).strip()
                status = "open"

                obs_url = f"obsidian://search?query={quote(title)}"

            items.append({
                "type": "obsidian",
                "title": title,
                "source_full": vault_path,
                "priority": priority,
                "due": due,
                "state": status,
                "tags": tags,
                "url": obs_url,
            })
    return items


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def _sort_key(item: dict):
    return (
        PRIORITY_ORDER.get(item["priority"], 3),
        item["due"] or "9999-99-99",
        item["source_full"],
        item["title"],
    )
