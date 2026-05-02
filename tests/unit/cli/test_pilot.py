"""
Unit tests for topgun.cli.pilot.

Covers pilot roster config resolution and the list command output.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from topgun.cli.pilot import DEFAULT_PILOTS, _get_default_pilot, _get_pilots, app

runner = CliRunner()


@pytest.fixture()
def config_file(tmp_path, monkeypatch):
    """Point CONFIG_FILE at a temp path for test isolation."""
    cfg = tmp_path / "config.json"
    monkeypatch.setattr("topgun.cli.pilot.CONFIG_FILE", cfg)
    return cfg


# ---------------------------------------------------------------------------
# Pilot roster resolution
# ---------------------------------------------------------------------------

def test_default_pilots_when_config_absent(config_file):
    """Missing config must fall back to the built-in DEFAULT_PILOTS list."""
    pilots = _get_pilots()
    assert pilots == DEFAULT_PILOTS


def test_custom_pilots_from_config(config_file):
    """Pilots configured in ona.pilots must be returned instead of defaults."""
    config_file.write_text(json.dumps({"ona": {"pilots": ["maverick", "rooster"]}}))
    pilots = _get_pilots()
    assert pilots == ["maverick", "rooster"]


def test_default_pilot_fallback(config_file):
    """Missing ona.default_pilot must fall back to 'maverick'."""
    assert _get_default_pilot() == "maverick"


def test_custom_default_pilot(config_file):
    """Configured ona.default_pilot must be returned correctly."""
    config_file.write_text(json.dumps({"ona": {"default_pilot": "ice"}}))
    assert _get_default_pilot() == "ice"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_pilot_list_shows_maverick(config_file):
    """'pilot list' must include maverick and label it team lead."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "maverick" in result.output
    assert "team lead" in result.output


def test_pilot_list_shows_all_defaults(config_file):
    """'pilot list' must display every pilot in the default roster."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    for pilot in DEFAULT_PILOTS:
        assert pilot in result.output


def test_pilot_list_custom_roster(config_file):
    """'pilot list' must show only the configured pilots."""
    config_file.write_text(json.dumps({"ona": {"pilots": ["maverick", "ice"]}}))
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "maverick" in result.output
    assert "ice" in result.output
    assert "rooster" not in result.output
