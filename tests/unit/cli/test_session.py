from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from topgun.cli.session import _format_size, app

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
