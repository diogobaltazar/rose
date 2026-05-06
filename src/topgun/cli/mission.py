"""topgun mission — plan, engage, and audit feature missions."""

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer

CONFIG_FILE = Path(
    os.environ.get("TOPGUN_CONFIG", str(Path.home() / ".config/topgun/config.json"))
)
_TOPGUN_DIR = Path(os.environ.get("TOPGUN_DIR", str(Path.home() / ".topgun")))
_MISSIONS_DIR = _TOPGUN_DIR / "mission"

from topgun.cli.theme import (
    console, make_table, ok, err, warn, dim, accent,
    SAGE, SMOKE, LEAF, WARN, ERR, PEARL, FERN, MOSS,
)

app = typer.Typer(
    name="mission",
    help="Plan, engage, and audit missions.",
    add_completion=False,
    invoke_without_command=True,
    rich_markup_mode=None,
)

DEFAULT_PILOTS = ["maverick", "rooster", "hangman", "ice", "phoenix", "payback", "fanboy", "bob"]
_TOPGUN_MISSION_TAG = "topgun-mission"


@app.callback()
def _mission_help(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _read_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _get_ona_config() -> dict:
    return _read_config().get("ona", {})


def _get_pilots() -> list[str]:
    return _get_ona_config().get("pilots", DEFAULT_PILOTS)


def _get_class_id() -> str | None:
    return _get_ona_config().get("class_id")


def _get_missions_repo() -> str | None:
    return _get_ona_config().get("missions_repo")


def _get_default_pilot() -> str:
    return _get_ona_config().get("default_pilot", "maverick")


# ---------------------------------------------------------------------------
# Mission fetching
# ---------------------------------------------------------------------------

def _fetch_github_missions() -> list[dict]:
    repo = _get_missions_repo()
    if not repo:
        return []
    token = os.environ.get("GITHUB_TOKEN", "")
    env = {**os.environ, "GITHUB_TOKEN": token} if token else os.environ
    result = subprocess.run(
        [
            "gh", "issue", "list",
            "--repo", repo,
            "--state", "open",
            "--json", "number,title,labels,createdAt,url",
            "--limit", "200",
        ],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        return []
    missions = []
    for issue in json.loads(result.stdout or "[]"):
        missions.append({
            "id": f"gh:{issue['number']}",
            "display_id": f"#{issue['number']}",
            "title": issue["title"],
            "source": "github",
            "repo": repo,
            "url": issue.get("url", f"https://github.com/{repo}/issues/{issue['number']}"),
            "created_at": issue.get("createdAt", ""),
        })
    return missions


def _fetch_obsidian_missions() -> list[dict]:
    import re
    from topgun.cli.backlog import _get_sources, _resolve_vault_path, _parse_frontmatter

    _FM_TAGS_RE = re.compile(r"tags:\s*\[([^\]]*)\]|tags:\s*(.+)", re.MULTILINE)

    sources = _get_sources()
    missions = []
    for s in sources:
        if s.get("type") != "obsidian":
            continue
        vault = _resolve_vault_path(s["path"])
        if not vault.exists():
            continue
        for md_file in vault.rglob("task.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            fm = _parse_frontmatter(text)
            tags_raw = fm.get("tags", "")
            tags: list[str] = []
            if tags_raw.startswith("["):
                tags = [t.strip().strip('"').strip("'") for t in tags_raw.strip("[]").split(",") if t.strip()]
            elif tags_raw:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            if _TOPGUN_MISSION_TAG not in tags:
                continue
            if fm.get("status", "open") != "open":
                continue
            title = ""
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            task_id = md_file.parent.name
            missions.append({
                "id": f"obs:{task_id}",
                "display_id": task_id[:20],
                "title": title or task_id,
                "source": "obsidian",
                "path": str(md_file),
                "url": "",
                "created_at": fm.get("date", ""),
            })
    return missions


def _fetch_all_missions() -> list[dict]:
    missions = []
    missions.extend(_fetch_github_missions())
    missions.extend(_fetch_obsidian_missions())
    return missions


def _resolve_mission(mission_id: str) -> dict | None:
    missions = _fetch_all_missions()
    if mission_id.isdigit():
        lookup = f"gh:{mission_id}"
    elif mission_id.startswith("#"):
        lookup = f"gh:{mission_id[1:]}"
    else:
        lookup = mission_id
    for m in missions:
        if m["id"] == lookup or m["display_id"] == mission_id:
            return m
    return None


def _get_mission_content(mission: dict) -> str:
    if mission["source"] == "github":
        result = subprocess.run(
            [
                "gh", "issue", "view", mission["id"].replace("gh:", ""),
                "--repo", mission["repo"], "--json", "body", "--jq", ".body",
            ],
            capture_output=True, text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    elif mission["source"] == "obsidian":
        try:
            return Path(mission["path"]).read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


# ---------------------------------------------------------------------------
# Engagement storage
# ---------------------------------------------------------------------------

def _engagement_dir(mission_id: str, engagement_id: str) -> Path:
    safe_id = mission_id.replace(":", "-")
    return _MISSIONS_DIR / safe_id / "engage" / engagement_id


def _write_engagement_meta(
    mission_id: str,
    engagement_id: str,
    pilot: str,
    mode: str,
    ona_env_id: str | None = None,
    ona_env_name: str | None = None,
    status: str = "running",
) -> Path:
    d = _engagement_dir(mission_id, engagement_id)
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "engagement_id": engagement_id,
        "mission_id": mission_id,
        "pilot": pilot,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "status": status,
        "mode": mode,
        "ona_env_id": ona_env_id,
        "ona_env_name": ona_env_name,
    }
    meta_file = d / "meta.json"
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")
    return d


def _update_engagement_status(engagement_dir: Path, status: str) -> None:
    meta_file = engagement_dir / "meta.json"
    if not meta_file.exists():
        return
    meta = json.loads(meta_file.read_text())
    meta["status"] = status
    meta["completed_at"] = datetime.now(timezone.utc).isoformat()
    meta_file.write_text(json.dumps(meta, indent=2) + "\n")


def _read_all_engagements(
    mission_filter: str | None = None,
    pilot_filter: str | None = None,
) -> list[dict]:
    engagements = []
    if not _MISSIONS_DIR.exists():
        return engagements
    for mission_dir in _MISSIONS_DIR.iterdir():
        if not mission_dir.is_dir():
            continue
        engage_root = mission_dir / "engage"
        if not engage_root.is_dir():
            continue
        for eng_dir in engage_root.iterdir():
            if not eng_dir.is_dir():
                continue
            meta_file = eng_dir / "meta.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text())
            except Exception:
                continue
            if mission_filter and meta.get("mission_id") != mission_filter:
                continue
            if pilot_filter and meta.get("pilot") != pilot_filter:
                continue
            engagements.append(meta)
    return sorted(engagements, key=lambda e: e.get("started_at", ""), reverse=True)


# ---------------------------------------------------------------------------
# ONA helpers
# ---------------------------------------------------------------------------

def _create_ona_env(env_name: str, class_id: str) -> str:
    """Create a blank ONA environment and return the environment ID."""
    result = subprocess.run(
        [
            "ona", "environment", "create", "from-scratch",
            "--class-id", class_id,
            "--name", env_name,
            "--dont-wait",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ona environment create failed")
    lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    env_id = lines[-1] if lines else ""
    if not env_id:
        raise RuntimeError("could not parse ONA environment ID from output")
    return env_id


def _wait_ona_ready(env_id: str, timeout: int = 300) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(
            ["ona", "environment", "get", env_id, "-o", "json"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            try:
                data = json.loads(r.stdout)
                phase = (data.get("phase") or data.get("status") or data.get("state") or "").lower()
                if phase == "running":
                    return
                if phase in ("failed", "deleted"):
                    raise RuntimeError(f"ONA environment entered phase: {phase}")
            except (json.JSONDecodeError, RuntimeError):
                raise
        time.sleep(5)
    raise RuntimeError(f"ONA environment not ready after {timeout}s")


def _rsync_logs(env_id: str, engagement_dir: Path) -> None:
    remote = f"{env_id}.ona.environment:~/.claude/projects/"
    local = str(engagement_dir / "claude" / "projects") + "/"
    Path(local).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rsync", "-az", "--timeout=30", remote, local],
        check=False,
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("plan")
def plan():
    """Open an interactive mission planning session."""
    import shutil
    claude_bin = shutil.which("claude")
    if not claude_bin:
        console.print(f"[{PEARL}]Run this on your host machine:[/{PEARL}]\n")
        console.print(f"  [{SAGE}]claude[/{SAGE}]\n")
        console.print(f"[{SMOKE}]Then type /topgun-mission-plan to start the planning session.[/{SMOKE}]")
        console.print(f"[{SMOKE}]Claude Code must be installed on the host — https://claude.ai/code[/{SMOKE}]")
        raise typer.Exit(0)
    console.print(f"[{SMOKE}]launching mission planning session — type /topgun-mission-plan to begin…[/{SMOKE}]")
    os.execvp(claude_bin, [claude_bin])


@app.command("list")
def list_cmd():
    """List all missions (GitHub topgun-missions issues + Obsidian topgun-mission tasks)."""
    missions = _fetch_all_missions()
    if not missions:
        console.print(f"[{SMOKE}]no missions found[/{SMOKE}]")
        console.print(
            f"[{SMOKE}]configure ona.missions_repo in ~/.config/topgun/config.json "
            f"or tag Obsidian tasks with #topgun-mission[/{SMOKE}]"
        )
        return

    table = make_table(
        ("ID", {"style": SAGE, "no_wrap": True}),
        ("Source", {"no_wrap": True}),
        ("Title", {}),
        ("Created", {"style": SMOKE, "no_wrap": True}),
    )

    for m in missions:
        src = f"[{FERN}]{m['source']}[/{FERN}]"
        created = (m.get("created_at") or "")[:10] or "—"
        url = m.get("url", "")
        title_cell = f"[link={url}]{m['title']}[/link]" if url else m["title"]
        table.add_row(m["display_id"], src, title_cell, created)

    console.print(table)


@app.command("engage")
def engage(
    args: Optional[List[str]] = typer.Argument(None),
    maverick: bool = typer.Option(False, "--maverick", help="Run locally as Maverick (no ONA)"),
    mission_filter: Optional[str] = typer.Option(None, "--mission", "-m", help="Filter by mission ID"),
    pilot_filter: Optional[str] = typer.Option(None, "--pilot", help="Filter by pilot name"),
):
    """Engage a mission, or manage engagements.

    \b
    topgun mission engage <mission-id>                engage in ONA
    topgun mission engage <mission-id> --maverick     engage locally as Maverick
    topgun mission engage list                        list all engagements
    topgun mission engage list --mission <id>         filter by mission
    topgun mission engage list --pilot <name>         filter by pilot
    topgun mission engage logs <engagement-id>        view engagement logs
    """
    if not args:
        console.print(f"[{PEARL}]Usage:[/{PEARL}]")
        console.print(f"  topgun mission engage [{SAGE}]<mission-id>[/{SAGE}]")
        console.print(f"  topgun mission engage [{SAGE}]<mission-id>[/{SAGE}] --maverick")
        console.print(f"  topgun mission engage list  [{SMOKE}]--mission <id>[/{SMOKE}]  [{SMOKE}]--pilot <name>[/{SMOKE}]")
        console.print(f"  topgun mission engage logs [{SAGE}]<engagement-id>[/{SAGE}]")
        return

    subcommand = args[0].lower()

    if subcommand == "list":
        _cmd_engage_list(mission_filter=mission_filter, pilot_filter=pilot_filter)
        return

    if subcommand == "logs":
        if len(args) < 2:
            console.print(f"[{ERR}]usage: topgun mission engage logs <engagement-id>[/{ERR}]")
            raise typer.Exit(1)
        _cmd_engage_logs(args[1])
        return

    _cmd_engage_start(args[0], maverick=maverick)


def _cmd_engage_list(mission_filter: str | None, pilot_filter: str | None) -> None:
    engagements = _read_all_engagements(mission_filter=mission_filter, pilot_filter=pilot_filter)
    if not engagements:
        console.print(f"[{SMOKE}]no engagements found[/{SMOKE}]")
        return

    table = make_table(
        ("ID", {"style": SAGE, "no_wrap": True}),
        ("Mission", {"no_wrap": True}),
        ("Pilot", {"no_wrap": True}),
        ("Mode", {"no_wrap": True}),
        ("Status", {"no_wrap": True}),
        ("Started", {"style": SMOKE, "no_wrap": True}),
    )

    _STATUS_COLOR = {"running": WARN, "success": LEAF, "failed": ERR}
    _MODE_COLOR = {"local": SAGE, "ona": FERN}

    for e in engagements:
        sc = _STATUS_COLOR.get(e.get("status", ""), SMOKE)
        mc = _MODE_COLOR.get(e.get("mode", ""), SMOKE)
        started = (e.get("started_at") or "")[:16].replace("T", " ")
        table.add_row(
            e["engagement_id"][:8],
            e.get("mission_id", "?"),
            e.get("pilot", "?"),
            f"[{mc}]{e.get('mode', '?')}[/{mc}]",
            f"[{sc}]{e.get('status', '?')}[/{sc}]",
            started,
        )

    console.print(table)


def _cmd_engage_logs(engagement_id: str) -> None:
    if not _MISSIONS_DIR.exists():
        console.print(f"[{SMOKE}]no engagements found[/{SMOKE}]")
        return

    matched_dir: Path | None = None
    matched_meta: dict | None = None
    for mission_dir in _MISSIONS_DIR.iterdir():
        if not mission_dir.is_dir():
            continue
        engage_root = mission_dir / "engage"
        if not engage_root.is_dir():
            continue
        for eng_dir in engage_root.iterdir():
            if eng_dir.name.startswith(engagement_id):
                meta_file = eng_dir / "meta.json"
                if meta_file.exists():
                    matched_dir = eng_dir
                    matched_meta = json.loads(meta_file.read_text())
                    break
        if matched_dir:
            break

    if not matched_dir:
        console.print(f"[{WARN}]no engagement found for:[/{WARN}] {engagement_id}")
        raise typer.Exit(1)

    if matched_meta and matched_meta.get("mode") == "ona" and matched_meta.get("ona_env_id"):
        console.print(f"[{SMOKE}]syncing logs from ONA…[/{SMOKE}]")
        _rsync_logs(matched_meta["ona_env_id"], matched_dir)

    claude_dir = matched_dir / "claude" / "projects"
    if not claude_dir.exists():
        console.print(f"[{SMOKE}]no logs found[/{SMOKE}]")
        return

    transcripts = list(claude_dir.rglob("*.jsonl"))
    if not transcripts:
        console.print(f"[{SMOKE}]no transcript files found[/{SMOKE}]")
        return

    transcripts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    transcript = transcripts[0]
    console.print(f"[{SMOKE}]{transcript}[/{SMOKE}]\n")

    with transcript.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = event.get("role", "")
            content = event.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")[:300]
                        if role == "assistant":
                            console.print(f"[{SAGE}]▶[/{SAGE}] {text}")
                        elif role == "user":
                            console.print(f"[{SMOKE}]◀ {text}[/{SMOKE}]")
            elif isinstance(content, str) and content:
                text = content[:300]
                if role == "assistant":
                    console.print(f"[{SAGE}]▶[/{SAGE}] {text}")


def _cmd_engage_start(mission_id: str, maverick: bool) -> None:
    mission = _resolve_mission(mission_id)
    if not mission:
        console.print(f"[{WARN}]mission not found:[/{WARN}] {mission_id}")
        console.print(f"[{SMOKE}]run: topgun mission list[/{SMOKE}]")
        raise typer.Exit(1)

    engagement_id = str(uuid.uuid4())
    pilot = _get_default_pilot()
    mode = "local" if maverick else "ona"
    safe_mission_id = mission["id"].replace(":", "-")
    env_name = f"mission-{safe_mission_id}-engage-{engagement_id[:8]}"

    console.print(f"\n  [{SMOKE}]mission[/{SMOKE}]  {mission['title']}")
    console.print(f"  [{SMOKE}]pilot[/{SMOKE}]    [{SAGE}]{pilot}[/{SAGE}]")
    console.print(f"  [{SMOKE}]mode[/{SMOKE}]     {mode}")
    console.print(f"  [{SMOKE}]engage[/{SMOKE}]   {engagement_id[:8]}\n")

    if maverick:
        eng_dir = _write_engagement_meta(mission["id"], engagement_id, pilot, "local")
        content = _get_mission_content(mission)
        if not content:
            console.print(f"[{ERR}]could not retrieve mission content[/{ERR}]")
            _update_engagement_status(eng_dir, "failed")
            raise typer.Exit(1)
        console.print(f"[{SMOKE}]engaging locally…[/{SMOKE}]")
        result = subprocess.run(["claude", "--dangerously-skip-permissions", "-p", content])
        status = "success" if result.returncode == 0 else "failed"
        _update_engagement_status(eng_dir, status)
        color = LEAF if status == "success" else ERR
        console.print(f"\n[{color}]{status}[/{color}]  {engagement_id[:8]}")
        return

    # ONA execution
    class_id = _get_class_id()
    if not class_id:
        console.print(f"[{ERR}]ona.class_id is required in ~/.config/topgun/config.json[/{ERR}]")
        console.print(f'[{SMOKE}]add: {{ "ona": {{ "class_id": "<your-class-id>" }} }}[/{SMOKE}]')
        raise typer.Exit(1)

    eng_dir = _write_engagement_meta(mission["id"], engagement_id, pilot, "ona", ona_env_name=env_name)

    try:
        console.print(f"[{SMOKE}]creating ONA environment…[/{SMOKE}]")
        env_id = _create_ona_env(env_name, class_id)

        meta_file = eng_dir / "meta.json"
        meta = json.loads(meta_file.read_text())
        meta["ona_env_id"] = env_id
        meta_file.write_text(json.dumps(meta, indent=2) + "\n")

        console.print(f"[{SMOKE}]environment: {env_id}[/{SMOKE}]")
        console.print(f"[{SMOKE}]waiting for environment…[/{SMOKE}]")
        _wait_ona_ready(env_id)

        if mission["source"] == "github":
            prompt = (
                f"Fetch and execute the mission plan at: {mission['url']}\n\n"
                "Execute the full development flow autonomously. "
                "Do not stop until a PR is created."
            )
        else:
            content = _get_mission_content(mission)
            prompt = (
                f"{content}\n\n"
                "Execute this mission using the full development flow. "
                "Do not stop until a PR is created."
            )

        console.print(f"[{SMOKE}]launching Claude Code…[/{SMOKE}]")
        exec_result = subprocess.run([
            "ona", "environment", "exec", env_id,
            "--timeout", "3600",
            "--", "claude", "--dangerously-skip-permissions", "-p", prompt,
        ])

        console.print(f"[{SMOKE}]syncing logs…[/{SMOKE}]")
        _rsync_logs(env_id, eng_dir)

        status = "success" if exec_result.returncode == 0 else "failed"
        _update_engagement_status(eng_dir, status)
        color = LEAF if status == "success" else ERR
        console.print(f"\n[{color}]{status}[/{color}]  {engagement_id[:8]}  {env_name}")

    except Exception as e:
        _update_engagement_status(eng_dir, "failed")
        console.print(f"[{ERR}]engagement failed:[/{ERR}] {e}")
        raise typer.Exit(1)
