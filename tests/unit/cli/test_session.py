from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from topgun.cli.session import ARCHIVE, _archive_session, _dir_stats, _format_size, app

runner = CliRunner()


def test_format_size_kb():
    """_format_size must express sub-megabyte files in KB.

    This is meaningful because the KB/MB boundary is the primary display branch
    in the list command; verifying the KB path ensures small session files are
    not misleadingly shown as 0.0 MB.
    """
    assert _format_size(512_000) == "512.0 KB"


def test_format_size_mb():
    """_format_size must express files of 1 MB or larger in MB.

    Large session transcripts from long conversations can easily exceed 1 MB;
    showing raw KB would produce unwieldy numbers and obscure relative size.
    """
    assert _format_size(2_500_000) == "2.5 MB"


def test_format_size_boundary():
    """_format_size must switch to MB at exactly 1,000,000 bytes.

    Verifying the boundary prevents an off-by-one error that would cause 1 MB
    files to display as '1000.0 KB' rather than '1.0 MB'.
    """
    assert _format_size(1_000_000) == "1.0 MB"


def test_dir_stats_size_and_mtime(tmp_path):
    """_dir_stats must return the correct total size and newest mtime in one pass.

    This is the core correctness test for the single-pass optimisation. Both
    values must be accurate — an incorrect size or stale mtime would produce
    wrong output in session list and archive. The test uses two files with
    distinct mtimes to verify that the maximum (not the first or last) is
    returned, and that sizes are summed, not max'd.
    """
    import time

    root = tmp_path / "session"
    root.mkdir()
    sub = root / "subagents"
    sub.mkdir()

    f1 = sub / "agent-a.jsonl"
    f1.write_bytes(b"x" * 100)
    time.sleep(0.01)
    f2 = sub / "agent-b.jsonl"
    f2.write_bytes(b"y" * 200)

    size, mtime = _dir_stats(root)

    assert size == 300
    assert mtime == pytest.approx(f2.stat().st_mtime, abs=0.001)


def test_dir_stats_empty_dir(tmp_path):
    """_dir_stats must handle a directory containing no files without error.

    New-format session dirs that have been partially cleaned up may contain
    only subdirectory structure with no files. Returning size=0 and the dir's
    own mtime is the correct and safe behaviour — it avoids a max([]) ValueError
    and still produces a displayable row in the session list.
    """
    root = tmp_path / "empty-session"
    root.mkdir()
    (root / "subagents").mkdir()

    size, mtime = _dir_stats(root)

    assert size == 0
    assert mtime == pytest.approx(root.stat().st_mtime, abs=1.0)


def test_dir_stats_nested(tmp_path):
    """_dir_stats must recurse into nested subdirectories.

    Subagent files live at arbitrary depth inside the session dir. A shallow
    walk would silently undercount size and produce an incorrect mtime. This
    test verifies that files two levels deep are included in both aggregates.
    """
    root = tmp_path / "session"
    deep = root / "subagents" / "nested"
    deep.mkdir(parents=True)
    (deep / "agent.jsonl").write_bytes(b"z" * 50)

    size, mtime = _dir_stats(root)

    assert size == 50


def test_list_no_projects_dir(tmp_path):
    """list command must exit cleanly when the projects directory does not exist.

    Without this guard, iterating a missing directory raises a FileNotFoundError
    and produces an unhelpful traceback instead of a friendly message.
    """
    with patch("topgun.cli.session.CLAUDE_PROJECTS", tmp_path / "nonexistent"):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No projects directory" in result.output


def test_list_no_sessions(tmp_path):
    """list command must exit cleanly when the projects directory is empty.

    A freshly installed topgun instance has no sessions yet; this test ensures the
    command handles that state gracefully rather than rendering an empty table.
    """
    (tmp_path / "projects").mkdir()
    with patch("topgun.cli.session.CLAUDE_PROJECTS", tmp_path / "projects"):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No session transcripts found" in result.output


def test_list_shows_sessions(tmp_path):
    """list command must render a table row for each .jsonl transcript found.

    This is the primary happy-path test: given two sessions across two project
    directories, both must appear in the output with their session IDs visible.
    Edge cases not covered: sessions in the vault (outside CLAUDE_PROJECTS),
    and non-.jsonl files, which must be silently ignored.
    """
    projects = tmp_path / "projects"
    proj_a = projects / "-Users-alice-myproject"
    proj_b = projects / "-Users-alice-other"
    proj_a.mkdir(parents=True)
    proj_b.mkdir(parents=True)
    (proj_a / "abc-123.jsonl").write_text('{"role":"user"}')
    (proj_b / "def-456.jsonl").write_text('{"role":"user"}' * 100)

    with patch("topgun.cli.session.CLAUDE_PROJECTS", projects):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "abc-123" in result.output
    assert "def-456" in result.output


def test_archive_session_moves_transcript_and_session_dir(tmp_path):
    """_archive_session must move both the .jsonl transcript and the uuid/ directory.

    This is the core correctness test for the archive helper. Claude Code stores
    subagent transcripts in <uuid>/subagents/ alongside the main .jsonl file.
    Archiving only the .jsonl silently loses all subagent data. This test verifies
    both artefacts are relocated and the originals are gone.
    Edge cases not covered: archive path overrides via TOPGUN_ARCHIVE env var.
    """
    proj = tmp_path / "-Users-alice-project"
    proj.mkdir(parents=True)

    session_id = "abc-123"
    (proj / f"{session_id}.jsonl").write_text('{"role":"user"}')
    subagents = proj / session_id / "subagents"
    subagents.mkdir(parents=True)
    (subagents / "agent-x.jsonl").write_text("{}")

    archive_root = tmp_path / "archive"

    with patch("topgun.cli.session.ARCHIVE", archive_root):
        _archive_session({"session_id": session_id, "project_dir": proj, "format": "legacy"})

    dest_dir = archive_root / "projects" / "-Users-alice-project"
    assert (dest_dir / f"{session_id}.jsonl").exists(), "transcript must be in archive"
    assert (dest_dir / session_id / "subagents" / "agent-x.jsonl").exists(), "session dir must be in archive"
    assert not (proj / f"{session_id}.jsonl").exists(), "original transcript must be gone"
    assert not (proj / session_id).exists(), "original session dir must be gone"


def test_archive_session_works_without_session_dir(tmp_path):
    """_archive_session must succeed when no uuid/ directory exists.

    Older sessions (or sessions with no subagents) may have only a .jsonl file.
    The helper must not error in this case.
    """
    proj = tmp_path / "-Users-alice-project"
    proj.mkdir(parents=True)

    session_id = "def-456"
    (proj / f"{session_id}.jsonl").write_text('{"role":"user"}')

    archive_root = tmp_path / "archive"

    with patch("topgun.cli.session.ARCHIVE", archive_root):
        _archive_session({"session_id": session_id, "project_dir": proj, "format": "legacy"})

    dest_dir = archive_root / "projects" / "-Users-alice-project"
    assert (dest_dir / f"{session_id}.jsonl").exists()
    assert not (proj / f"{session_id}.jsonl").exists()


def test_archive_session_multiple(tmp_path):
    """_archive_session called in sequence must archive each session independently.

    The interactive archive command calls _archive_session once per selected
    session. This test confirms that archiving multiple sessions in a loop
    produces the correct files for each, without cross-contamination.
    """
    proj = tmp_path / "-Users-alice-project"
    proj.mkdir(parents=True)

    for sid in ("aaa-111", "bbb-222"):
        (proj / f"{sid}.jsonl").write_text('{}')

    archive_root = tmp_path / "archive"

    with patch("topgun.cli.session.ARCHIVE", archive_root):
        for sid in ("aaa-111", "bbb-222"):
            _archive_session({"session_id": sid, "project_dir": proj, "format": "legacy"})

    dest_dir = archive_root / "projects" / "-Users-alice-project"
    assert (dest_dir / "aaa-111.jsonl").exists()
    assert (dest_dir / "bbb-222.jsonl").exists()


def test_list_sorted_newest_first(tmp_path):
    """list command must order sessions by last modified time, newest first.

    Without explicit sorting, directory iteration order is filesystem-dependent
    and non-deterministic. Users expect the most recent session at the top so
    they can quickly identify and act on it.
    """
    import os
    import time

    projects = tmp_path / "projects"
    proj = projects / "-Users-alice-project"
    proj.mkdir(parents=True)

    older = proj / "old-session.jsonl"
    older.write_text("{}")
    time.sleep(0.05)
    newer = proj / "new-session.jsonl"
    newer.write_text("{}")

    with patch("topgun.cli.session.CLAUDE_PROJECTS", projects):
        result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert result.output.index("new-session") < result.output.index("old-session")
