#!/usr/bin/env python3
"""
rose observe — session inspector

Usage:
  python scripts/observe.py --list    # list all sessions
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
SESSIONS_DIR = Path.home() / ".claude" / "sessions"

# ── ANSI ──────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
BLINK  = "\033[5m"

# Matrix palette — blacks, pearls, neon greens
NEON         = "\033[38;5;118m"  # live dot / session ID — bright neon green
NEON_DIM     = "\033[38;5;28m"   # branch / worktree     — deep matrix green
PEARL        = "\033[38;5;253m"  # title                 — pearl white
SILVER       = "\033[38;5;245m"  # resumed ←             — silver

YELLOW = SILVER   # fallback for fmt_dot unknown


# ── Git helpers ───────────────────────────────────────────────────────────────

def git(cwd: str, *args) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def git_info(cwd: str) -> dict:
    """Return project root and worktree path for a given cwd."""
    if not cwd or not Path(cwd).exists():
        return {"project": None, "worktree": None}

    git_dir = git(cwd, "rev-parse", "--git-dir")
    if not git_dir:
        return {"project": None, "worktree": None}

    # A worktree's --git-dir looks like /path/to/repo/.git/worktrees/<name>
    is_worktree = "/.git/worktrees/" in git_dir or git_dir.endswith("/worktrees")

    if is_worktree:
        # Common dir points to the main repo's .git
        common_dir = git(cwd, "rev-parse", "--git-common-dir")
        if common_dir:
            project = str(Path(common_dir).resolve().parent)
        else:
            project = None
        worktree = git(cwd, "rev-parse", "--show-toplevel")
    else:
        project  = git(cwd, "rev-parse", "--show-toplevel")
        worktree = None

    return {"project": project, "worktree": worktree}


# ── Native session storage ────────────────────────────────────────────────────

def pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def encode_cwd(cwd: str) -> str:
    """Encode a cwd path to a Claude project directory name (/ → -)."""
    return cwd.replace("/", "-")


def live_transcripts() -> dict[str, dict]:
    """Return {transcript_stem: {pid, sessionId}} for all live processes.

    sessionId in sessions/{pid}.json is the process identity, NOT the transcript
    filename — they diverge on resume. Instead we match by finding the transcript
    in the project dir with mtime >= startedAt (ms).
    """
    result = {}
    if not SESSIONS_DIR.exists():
        return result
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            data       = json.loads(f.read_text())
            pid        = data.get("pid")
            sid        = data.get("sessionId")
            cwd        = data.get("cwd", "")
            started_ms = data.get("startedAt", 0)
        except (json.JSONDecodeError, OSError):
            continue

        if not pid or not cwd:
            continue
        if not pid_running(pid):
            continue

        started_s   = started_ms / 1000
        project_dir = PROJECTS_DIR / encode_cwd(cwd)
        if not project_dir.exists():
            continue

        for transcript in project_dir.glob("*.jsonl"):
            if transcript.stat().st_mtime >= started_s:
                result[transcript.stem] = {"pid": pid, "sessionId": sid}
                break

    return result


# ── Transcript reading ────────────────────────────────────────────────────────

def strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>[^<]*</[^>]+>", "", text)
    cleaned = re.sub(r"<[^>]+/>", "", cleaned)
    return cleaned.strip()


def read_transcript(path: Path) -> dict:
    """Extract cwd, branch, started_at, ended_at, title from a transcript."""
    title      = None
    branch     = None
    cwd        = None
    started_at = None
    ended_at   = None

    try:
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if started_at is None:
                        started_at = ts
                    ended_at = ts

                if entry.get("type") == "user" and entry.get("message", {}).get("role") == "user":
                    if cwd is None:
                        cwd = entry.get("cwd")
                    if branch is None:
                        branch = entry.get("gitBranch")
                    if title is None:
                        content = entry.get("message", {}).get("content", "")
                        if isinstance(content, str):
                            cleaned = strip_tags(content)
                            if cleaned:
                                title = cleaned
    except OSError:
        pass

    return {
        "cwd":        cwd,
        "branch":     branch,
        "started_at": started_at,
        "ended_at":   ended_at,
        "title":      title,
        "size_kb":    round(path.stat().st_size / 1024, 1),
    }


# ── Session scanning ──────────────────────────────────────────────────────────

def scan_sessions() -> list[dict]:
    live         = live_transcripts()  # {transcript_stem: {pid, sessionId}}
    sessions     = []
    matched_pids = set()

    if PROJECTS_DIR.exists():
        for project_dir in PROJECTS_DIR.iterdir():
            if not project_dir.is_dir():
                continue
            for transcript in project_dir.glob("*.jsonl"):
                session_id = transcript.stem
                info       = read_transcript(transcript)
                gi         = git_info(info["cwd"] or "")

                if session_id in live:
                    status      = "live"
                    pid         = live[session_id]["pid"]
                    process_sid = live[session_id]["sessionId"]
                    matched_pids.add(pid)
                else:
                    status      = "done"
                    pid         = None
                    process_sid = None

                sessions.append({
                    "session_id":  session_id,
                    "process_sid": process_sid,
                    "pid":         pid,
                    "status":      status,
                    "project":     gi["project"],
                    "worktree":    gi["worktree"],
                    "branch":      info["branch"],
                    "started_at":  info["started_at"],
                    "title":       info["title"],
                    "size_kb":     info["size_kb"],
                })

    # Live processes with no transcript yet
    if SESSIONS_DIR.exists():
        for f in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                pid  = data.get("pid")
                sid  = data.get("sessionId")
                cwd  = data.get("cwd", "")
                ms   = data.get("startedAt", 0)
            except (json.JSONDecodeError, OSError):
                continue
            if not pid or not pid_running(pid) or pid in matched_pids:
                continue
            gi = git_info(cwd)
            sessions.append({
                "session_id":  sid,
                "process_sid": None,
                "pid":         pid,
                "status":      "live",
                "project":     gi["project"] or cwd,
                "worktree":    gi["worktree"],
                "branch":      git(cwd, "rev-parse", "--abbrev-ref", "HEAD"),
                "started_at":  datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(),
                "title":       None,
                "size_kb":     None,
            })

    sessions.sort(key=lambda s: s["started_at"] or "", reverse=True)
    return sessions


# ── Formatting ────────────────────────────────────────────────────────────────

def fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%d-%b-%Y %H:%M:%S").upper()
    except Exception:
        return iso[:19]


def fmt_project(path: str | None) -> str:
    if not path:
        return f"{DIM}—{RESET}"
    p = Path(path)
    parent = str(p.parent) + "/"
    name   = p.name
    return f"{DIM}{parent}{RESET}{BOLD}{name}{RESET}"


def fmt_worktree(path: str | None) -> str:
    if not path:
        return f"{DIM}—{RESET}"
    return Path(path).name


SEP = f"  {DIM}{'─' * 72}{RESET}"


def fmt_dot(status: str) -> str:
    if status == "live":
        return f"{BLINK}{NEON}●{RESET}"
    elif status == "unknown":
        return f"{SILVER}●{RESET}"
    else:
        return f"{DIM}○{RESET}"


def list_sessions():
    sessions = scan_sessions()

    if not sessions:
        print("\n  no sessions found\n")
        return

    print()
    for s in sessions:
        status   = s["status"]
        sid      = f"{BOLD}{NEON}{s['session_id']}{RESET}"
        psid     = s.get("process_sid", "")
        resumed  = f"{SILVER}←{DIM}{psid}{RESET}" if psid and psid != s["session_id"] else ""
        pid      = f"{DIM}pid {s['pid']}{RESET}" if s["pid"] else ""
        started  = fmt_dt(s["started_at"])
        project  = fmt_project(s["project"])
        worktree = s["worktree"] and f"{NEON_DIM}worktree {fmt_worktree(s['worktree'])}{RESET}"
        branch   = f"{NEON_DIM}⎇ {s['branch']}{RESET}" if s["branch"] else None
        title    = f"{PEARL}{s['title']}{RESET}" if s["title"] else ""
        if s["size_kb"] is None:
            size = "0 KB"
        elif s["size_kb"] >= 1024:
            size = f"{s['size_kb'] / 1024:.1f} MB"
        else:
            size = f"{s['size_kb']} KB"

        meta_parts = [p for p in [project, branch, worktree, f"{DIM}{started}{RESET}", f"{DIM}{size}{RESET}"] if p]
        meta = f"  {DIM}·{RESET}  ".join(str(p) for p in meta_parts)

        print(SEP)
        header = "  ".join(filter(None, [sid, resumed, pid]))
        print(f"  {fmt_dot(status)}  {header}")
        print(f"  {title}")
        print(f"  {meta}")
        print()

    print(SEP)
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_sessions()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
