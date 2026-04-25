"""
Unit tests for topgun.cli.notes.

Covers the config read/write helpers that manage notes.sources in
~/.config/topgun/config.json. These are the critical units: if config
management is wrong, topgun notes track/untrack/sources all misbehave.
"""

import json
import sys
from pathlib import Path

import pytest

import topgun.cli.notes as notes_mod


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    """Redirect CONFIG_FILE to a temp path and return it."""
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(notes_mod, "CONFIG_FILE", cfg)
    return cfg


def test_read_config_missing_returns_empty(config_path):
    """_read_config must return {} when the file does not exist.

    notes.py calls _read_config at the top of every command. A missing
    config must never raise — it is a valid first-run state.
    """
    assert notes_mod._read_config() == {}


def test_read_config_invalid_json_returns_empty(config_path):
    """_read_config must return {} when the file contains invalid JSON.

    A corrupted config must degrade gracefully so the user can at least
    run topgun notes track to rebuild it.
    """
    config_path.write_text("not json")
    assert notes_mod._read_config() == {}


def test_get_sources_empty_when_no_notes_key(config_path):
    """_get_sources returns [] when config exists but has no 'notes' key.

    This covers the case where the user has a backlog config but has not
    yet run topgun notes track.
    """
    config_path.write_text(json.dumps({"backlog": {"sources": []}}))
    assert notes_mod._get_sources() == []


def test_get_sources_returns_notes_sources(config_path):
    """_get_sources returns the notes.sources list from config.

    The slash command and all CLI subcommands call this to find vaults.
    Wrong results here break every notes operation.
    """
    sources = [{"type": "obsidian", "path": "/some/vault", "description": "test"}]
    config_path.write_text(json.dumps({"notes": {"sources": sources}}))
    assert notes_mod._get_sources() == sources


def test_write_config_creates_parent_dirs(tmp_path, monkeypatch):
    """_write_config must create parent directories if they don't exist.

    The config directory (~/.config/topgun/) may not exist on a fresh
    install. Failing silently here would corrupt the config silently.
    """
    cfg = tmp_path / "nested" / "dir" / "config.json"
    monkeypatch.setattr(notes_mod, "CONFIG_FILE", cfg)
    notes_mod._write_config({"notes": {"sources": []}})
    assert cfg.exists()
    assert json.loads(cfg.read_text()) == {"notes": {"sources": []}}
