"""
Unit tests for topgun.cli.mission.

Covers engagement metadata read/write, mission ID resolution, pilot config
defaults, and the engage list/logs dispatch routing.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from topgun.cli.mission import (
    DEFAULT_PILOTS,
    _engagement_dir,
    _read_all_engagements,
    _update_engagement_status,
    _write_engagement_meta,
    app,
)

runner = CliRunner()


@pytest.fixture()
def missions_dir(tmp_path, monkeypatch):
    """Redirect _MISSIONS_DIR to a temp path for isolation."""
    d = tmp_path / "mission"
    d.mkdir()
    monkeypatch.setattr("topgun.cli.mission._MISSIONS_DIR", d)
    return d


# ---------------------------------------------------------------------------
# Engagement metadata
# ---------------------------------------------------------------------------

def test_write_and_read_engagement_meta(missions_dir):
    """Written engagement metadata must be recoverable via _read_all_engagements."""
    eng_id = "aaaaaaaa-0000-0000-0000-000000000001"
    _write_engagement_meta("gh-42", eng_id, "maverick", "local")

    engagements = _read_all_engagements()
    assert len(engagements) == 1
    e = engagements[0]
    assert e["engagement_id"] == eng_id
    assert e["mission_id"] == "gh-42"
    assert e["pilot"] == "maverick"
    assert e["mode"] == "local"
    assert e["status"] == "running"
    assert e["completed_at"] is None


def test_update_engagement_status_to_success(missions_dir):
    """Updating status must persist completed_at and the new status."""
    eng_id = "bbbbbbbb-0000-0000-0000-000000000002"
    eng_dir = _write_engagement_meta("gh-42", eng_id, "maverick", "local")
    _update_engagement_status(eng_dir, "success")

    meta = json.loads((eng_dir / "meta.json").read_text())
    assert meta["status"] == "success"
    assert meta["completed_at"] is not None


def test_update_engagement_status_missing_file(tmp_path):
    """Updating status when meta.json is absent must not raise."""
    _update_engagement_status(tmp_path / "nonexistent", "success")


def test_engagement_dir_sanitises_colon(missions_dir):
    """Mission IDs with ':' must be converted to '-' in the filesystem path."""
    eng_id = "cccccccc-0000-0000-0000-000000000003"
    d = _engagement_dir("gh:42", eng_id)
    assert ":" not in str(d)
    assert "gh-42" in str(d)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def test_filter_by_mission(missions_dir):
    """_read_all_engagements must return only engagements matching mission_filter."""
    _write_engagement_meta("gh-42", "aa" * 16 + "01", "maverick", "local")
    _write_engagement_meta("gh-99", "aa" * 16 + "02", "maverick", "local")

    results = _read_all_engagements(mission_filter="gh-42")
    assert all(e["mission_id"] == "gh-42" for e in results)
    assert len(results) == 1


def test_filter_by_pilot(missions_dir):
    """_read_all_engagements must return only engagements for the given pilot."""
    _write_engagement_meta("gh-42", "aa" * 16 + "03", "maverick", "local")
    _write_engagement_meta("gh-42", "aa" * 16 + "04", "rooster", "ona")

    results = _read_all_engagements(pilot_filter="rooster")
    assert len(results) == 1
    assert results[0]["pilot"] == "rooster"


def test_empty_missions_dir_returns_empty(missions_dir):
    """An empty missions directory must produce an empty engagements list."""
    assert _read_all_engagements() == []


# ---------------------------------------------------------------------------
# CLI routing — engage subcommands
# ---------------------------------------------------------------------------

def test_engage_list_with_no_engagements(missions_dir):
    """'engage list' with no stored engagements must print a friendly message."""
    result = runner.invoke(app, ["engage", "list"])
    assert result.exit_code == 0
    assert "no engagements found" in result.output


def test_engage_logs_missing_id(missions_dir):
    """'engage logs' without an argument must exit non-zero."""
    result = runner.invoke(app, ["engage", "logs"])
    assert result.exit_code != 0


def test_engage_logs_unknown_id(missions_dir):
    """'engage logs' with an unknown engagement ID must exit non-zero."""
    result = runner.invoke(app, ["engage", "logs", "nonexistent"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Default pilot roster
# ---------------------------------------------------------------------------

def test_default_pilots_contains_maverick():
    """Maverick must always be in the default pilot roster."""
    assert "maverick" in DEFAULT_PILOTS


def test_default_pilots_non_empty():
    """The default pilot roster must have at least one entry."""
    assert len(DEFAULT_PILOTS) > 0
