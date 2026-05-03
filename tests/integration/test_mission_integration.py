"""
Integration tests for the mission system.

Tests the ~/.topgun/mission/{id}/engage/{id}/ directory structure end-to-end,
and validates that config schema reads/writes correctly for ona.* fields.

What is tested:
  - Full write/read/update cycle for engagement metadata on disk
  - Directory layout matches the expected ~/.topgun/mission/{id}/engage/{id}/ structure
  - Multiple engagements across multiple missions can coexist without collision
  - Config schema: ona.class_id, ona.pilots, ona.default_pilot, ona.missions_repo

What is explicitly NOT tested:
  - ONA CLI calls (requires authenticated ONA session)
  - gh CLI calls (requires GitHub credentials)
  - claude CLI calls (requires Anthropic API key)
"""

import json
import uuid
from pathlib import Path

import pytest

from topgun.cli.mission import (
    _engagement_dir,
    _read_all_engagements,
    _update_engagement_status,
    _write_engagement_meta,
)
from topgun.cli.pilot import _get_default_pilot, _get_pilots


@pytest.fixture()
def isolated_missions(tmp_path, monkeypatch):
    d = tmp_path / "mission"
    d.mkdir()
    monkeypatch.setattr("topgun.cli.mission._MISSIONS_DIR", d)
    return d


@pytest.fixture()
def config_file(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr("topgun.cli.pilot.CONFIG_FILE", cfg)
    monkeypatch.setattr("topgun.cli.mission.CONFIG_FILE", cfg)
    return cfg


# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------

def test_engagement_layout_matches_spec(isolated_missions):
    """Engagement directories must follow ~/.topgun/mission/{id}/engage/{id}/ layout.

    This structure is load-bearing: topgun mission engage list and logs commands
    traverse it by convention. Any deviation breaks listing and log retrieval.
    """
    mission_id = "gh-42"
    eng_id = str(uuid.uuid4())
    eng_dir = _write_engagement_meta(mission_id, eng_id, "maverick", "local")

    expected = isolated_missions / "gh-42" / "engage" / eng_id
    assert eng_dir == expected
    assert (eng_dir / "meta.json").exists()


def test_multiple_missions_do_not_collide(isolated_missions):
    """Engagements for different missions must live in separate directories.

    A collision here would cause topgun mission engage list to return engagements
    from the wrong mission when filtering by --mission.
    """
    e1 = str(uuid.uuid4())
    e2 = str(uuid.uuid4())
    _write_engagement_meta("gh-1", e1, "maverick", "local")
    _write_engagement_meta("gh-2", e2, "maverick", "local")

    assert (isolated_missions / "gh-1" / "engage" / e1).exists()
    assert (isolated_missions / "gh-2" / "engage" / e2).exists()

    m1 = _read_all_engagements(mission_filter="gh-1")
    m2 = _read_all_engagements(mission_filter="gh-2")
    assert len(m1) == 1 and m1[0]["mission_id"] == "gh-1"
    assert len(m2) == 1 and m2[0]["mission_id"] == "gh-2"


def test_engagement_status_lifecycle(isolated_missions):
    """An engagement must transition correctly from running → success on disk.

    The status field drives topgun mission engage list display. A stale
    'running' status after completion would mislead the operator.
    """
    eng_id = str(uuid.uuid4())
    eng_dir = _write_engagement_meta("gh-42", eng_id, "maverick", "ona")

    meta_before = json.loads((eng_dir / "meta.json").read_text())
    assert meta_before["status"] == "running"
    assert meta_before["completed_at"] is None

    _update_engagement_status(eng_dir, "success")

    meta_after = json.loads((eng_dir / "meta.json").read_text())
    assert meta_after["status"] == "success"
    assert meta_after["completed_at"] is not None


# ---------------------------------------------------------------------------
# Config schema
# ---------------------------------------------------------------------------

def test_ona_class_id_read_from_config(config_file):
    """ona.class_id must be readable from config.json.

    topgun mission engage fails fast if this field is absent. The config
    schema must support it at the ona.class_id path.
    """
    config_file.write_text(json.dumps({"ona": {"class_id": "test-class-xyz"}}))
    from topgun.cli.mission import _get_class_id
    assert _get_class_id() == "test-class-xyz"


def test_ona_pilots_read_from_config(config_file):
    """ona.pilots must be readable from config.json as a list.

    topgun pilot list reads from this field. The default roster is used when
    the field is absent.
    """
    config_file.write_text(json.dumps({"ona": {"pilots": ["maverick", "ice"]}}))
    pilots = _get_pilots()
    assert "maverick" in pilots
    assert "ice" in pilots


def test_ona_missions_repo_read_from_config(config_file):
    """ona.missions_repo must be readable from config.json.

    topgun mission list uses this to fetch GitHub missions. Without it,
    only Obsidian missions are shown.
    """
    config_file.write_text(json.dumps({"ona": {"missions_repo": "acme/topgun-missions"}}))
    from topgun.cli.mission import _get_missions_repo
    assert _get_missions_repo() == "acme/topgun-missions"


def test_ona_default_pilot_read_from_config(config_file):
    """ona.default_pilot must override the 'maverick' default.

    The default_pilot is recorded in every engagement's metadata and displayed
    in topgun mission engage list. It must round-trip through config correctly.
    """
    config_file.write_text(json.dumps({"ona": {"default_pilot": "rooster"}}))
    assert _get_default_pilot() == "rooster"
