import importlib
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from topgun.cli.observe import app

runner = CliRunner()


def test_watch_non_tty_prints_snapshot():
    """watch command must print a one-shot snapshot and exit cleanly when stdin is not a TTY.

    Without a TTY check, termios.tcgetattr raises termios.error: (25, 'Not a tty')
    when the command is run inside a Docker container or any non-interactive context.
    This test verifies that the command short-circuits before touching termios,
    calls scan_sessions and render_tabbed_view exactly once, and exits with code 0.
    Edge cases not covered: the full interactive TUI path (requires a real terminal),
    and the --web flag path (separate branch unrelated to TTY handling).
    """
    fake_sessions = [{"id": "test-session"}]
    fake_render   = MagicMock(return_value="snapshot output")

    with (
        patch("sys.stdin") as mock_stdin,
        patch("topgun.cli.observe.scan_sessions", return_value=fake_sessions) as mock_scan,
        patch("topgun.cli.observe.render_tabbed_view", return_value=fake_render()) as mock_render,
    ):
        mock_stdin.isatty.return_value = False
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    mock_scan.assert_called_once()
    mock_render.assert_called_once_with(fake_sessions, 0)


def test_paths_derive_from_claude_dir(tmp_path, monkeypatch):
    """When CLAUDE_DIR is set all six path constants must be rooted there.

    The topgun Docker service sets CLAUDE_DIR=/claude but does not set the
    individual PROJECTS_DIR / SESSIONS_DIR / … vars. Before this fix, observe.py
    fell back to Path.home() / ".claude" / … which resolves to /root/.claude/…
    inside the container — a path that does not exist — so live sessions were
    never detected. This test verifies that a single CLAUDE_DIR env var is
    sufficient to make all paths resolve correctly.
    Edge cases not covered: interaction between CLAUDE_DIR and an explicitly-set
    SESSIONS_DIR (that combination still works via the inner os.environ.get).
    """
    import topgun.cli.observe as obs_module

    monkeypatch.setenv("CLAUDE_DIR", str(tmp_path))
    for var in ("PROJECTS_DIR", "SESSIONS_DIR", "TEAMS_DIR",
                "SUBAGENT_LOG", "MESSAGE_LOG", "OBSERVE_CONFIG"):
        monkeypatch.delenv(var, raising=False)

    importlib.reload(obs_module)

    assert obs_module.PROJECTS_DIR   == tmp_path / "projects"
    assert obs_module.SESSIONS_DIR   == tmp_path / "sessions"
    assert obs_module.TEAMS_DIR      == tmp_path / "teams"
    assert obs_module.SUBAGENT_LOG   == tmp_path / "logs" / "subagent-events.jsonl"
    assert obs_module.MESSAGE_LOG    == tmp_path / "logs" / "message-events.jsonl"
    assert obs_module.OBSERVE_CONFIG == tmp_path / "observe-config.json"


def test_paths_fall_back_to_home_dot_claude(monkeypatch):
    """When CLAUDE_DIR is not set paths fall back to ~/.claude/… with no regression.

    This guards against the fix accidentally breaking host (non-Docker) usage
    where neither CLAUDE_DIR nor the individual path vars are set.
    """
    import topgun.cli.observe as obs_module

    for var in ("CLAUDE_DIR", "PROJECTS_DIR", "SESSIONS_DIR", "TEAMS_DIR",
                "SUBAGENT_LOG", "MESSAGE_LOG", "OBSERVE_CONFIG"):
        monkeypatch.delenv(var, raising=False)

    importlib.reload(obs_module)

    base = Path.home() / ".claude"
    assert obs_module.PROJECTS_DIR   == base / "projects"
    assert obs_module.SESSIONS_DIR   == base / "sessions"
    assert obs_module.TEAMS_DIR      == base / "teams"
    assert obs_module.SUBAGENT_LOG   == base / "logs" / "subagent-events.jsonl"
    assert obs_module.MESSAGE_LOG    == base / "logs" / "message-events.jsonl"
    assert obs_module.OBSERVE_CONFIG == base / "observe-config.json"


# ── read_transcript caching ─────────────────────────────────────────────────

def test_read_transcript_cache_hit(tmp_path):
    """A transcript whose mtime has not changed must be returned from cache without re-reading the file.

    The cache is the primary performance fix for #131: with 500+ sessions on disk
    read_transcript() was being called for every file on every refresh, taking ~6 s.
    Done sessions are immutable (append-only JSONL, process exited), so their mtime
    never changes. A cache hit avoids all file I/O for those sessions.
    This test verifies the invariant: same mtime → same object returned, file not re-opened.
    Edge cases not covered: concurrent modification (not possible in single-threaded refresh loop).
    """
    import topgun.cli.observe as obs

    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"user","timestamp":"2026-01-01T00:00:00Z","message":{"role":"user","content":"hi"},"cwd":"/tmp","gitBranch":"main"}\n')

    # Warm the cache with the first call.
    result_first = obs.read_transcript(transcript)

    # Patch open() to detect any re-read attempt.
    with patch("builtins.open", side_effect=AssertionError("file was re-opened on cache hit")):
        result_second = obs.read_transcript(transcript)

    assert result_first is result_second, "cache hit must return the identical dict object"


def test_read_transcript_cache_miss_on_mtime_change(tmp_path):
    """When a transcript's mtime changes the file must be re-parsed and the cache updated.

    Live sessions are being actively written to: their mtime advances with every appended
    message. This test verifies that a mtime change invalidates the cache entry and triggers
    a fresh parse, ensuring live session metrics stay current.
    Edge cases not covered: sub-second mtime resolution (platform-dependent, not relevant here).
    """
    import topgun.cli.observe as obs

    transcript = tmp_path / "session.jsonl"
    transcript.write_text('{"type":"user","timestamp":"2026-01-01T00:00:00Z","message":{"role":"user","content":"first"},"cwd":"/tmp","gitBranch":"main"}\n')

    result_first = obs.read_transcript(transcript)
    assert result_first["title"] == "first"

    # Simulate a new message appended — bump mtime by touching with a future timestamp.
    import time
    future = time.time() + 10
    os.utime(transcript, (future, future))
    transcript.write_text('{"type":"user","timestamp":"2026-01-01T00:01:00Z","message":{"role":"user","content":"second"},"cwd":"/tmp","gitBranch":"main"}\n')
    os.utime(transcript, (future, future))

    result_second = obs.read_transcript(transcript)
    assert result_second["title"] == "second", "stale cache must not be returned after mtime change"
    assert result_second is not result_first


# ── live_transcripts session ID lookup ──────────────────────────────────────

def test_live_transcripts_uses_session_id_not_glob(tmp_path, monkeypatch):
    """live_transcripts() must map the session's own transcript, not an arbitrary glob match.

    The previous implementation used glob() to find the first transcript in the project
    directory whose mtime was >= the session start time. Because glob() returns files in
    arbitrary order, it often stored a different session's ID as the live key, causing the
    actual running session to appear as "done" in the UI.

    The session file contains the sessionId, which equals the transcript filename. The fix
    looks up the transcript directly by path. This test places two transcripts in the same
    project directory and verifies that only the correct session ID is returned as live.
    Edge cases not covered: sessionId absent from session file (guarded by the not-sid check).
    """
    import topgun.cli.observe as obs
    import json

    sessions_dir = tmp_path / "sessions"
    projects_dir = tmp_path / "projects"
    sessions_dir.mkdir()
    project_dir = projects_dir / "-tmp-myproject"
    project_dir.mkdir(parents=True)

    # Two transcripts in the same project directory.
    (project_dir / "aaaa.jsonl").write_text("")
    (project_dir / "bbbb.jsonl").write_text("")

    # Session file points to "bbbb".
    session_file = sessions_dir / "1234.json"
    session_file.write_text(json.dumps({
        "pid": os.getpid(),  # use our own PID so pid_running() returns True
        "sessionId": "bbbb",
        "cwd": "/tmp/myproject",
        "startedAt": 0,
    }))

    monkeypatch.setattr(obs, "SESSIONS_DIR", sessions_dir)
    monkeypatch.setattr(obs, "PROJECTS_DIR", projects_dir)

    live = obs.live_transcripts()

    assert "bbbb" in live, "correct session ID must be in live map"
    assert "aaaa" not in live, "unrelated transcript must not be in live map"


def test_subagent_cache_hit(tmp_path):
    """A subagent JSONL file whose mtime has not changed must be returned from _subagent_cache without re-reading.

    read_subagents() parses every subagent JSONL on every refresh. With 485 subagent
    files totalling 52 MB in profiling, this accounted for ~9 s of the total scan time.
    Done subagents are immutable; their JSONL is never appended to after the agent exits.
    The _subagent_cache eliminates repeated I/O for those files.
    This test verifies that after a warm call, builtins.open is not called for the same file.
    Edge cases not covered: meta.json caching (small files, not a bottleneck).
    """
    import json
    import topgun.cli.observe as obs

    subagents_dir = tmp_path / "session" / "subagents"
    subagents_dir.mkdir(parents=True)

    meta = subagents_dir / "agent-abc123.meta.json"
    meta.write_text(json.dumps({"agentType": "general-purpose", "description": "test"}))

    jsonl = subagents_dir / "agent-abc123.jsonl"
    jsonl.write_text('{"type":"assistant","timestamp":"2026-01-01T00:00:00Z","message":{"content":[]}}\n')

    session_dir = tmp_path / "session"

    # Warm the cache.
    obs.read_subagents(session_dir, {}, set(), False, {}, {})

    with patch("builtins.open", side_effect=AssertionError("subagent file re-opened on cache hit")):
        obs.read_subagents(session_dir, {}, set(), False, {}, {})
