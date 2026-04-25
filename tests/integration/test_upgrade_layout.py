"""Integration tests for topgun upgrade file layout.

These tests run the full upgrade() function against a temporary directory and
assert that every file from global/ lands in the right place. They do not test
Claude behaviour — only that the installation layout is correct.
"""

import json
import sys
from pathlib import Path

import pytest

import topgun.cli.upgrade  # ensure it's registered in sys.modules

upgrade_mod = sys.modules["topgun.cli.upgrade"]

REPO_ROOT = Path(__file__).parent.parent.parent
GLOBAL_SRC = REPO_ROOT / "global"


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect Path.home() to a temp directory for the duration of the test."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


@pytest.fixture
def installed(tmp_path, fake_home, monkeypatch):
    """Run upgrade() against a fresh temp directory and return that directory."""
    monkeypatch.setattr(upgrade_mod, "ROSE_DIR", REPO_ROOT)
    upgrade_mod.upgrade(claude_dir=tmp_path)
    return tmp_path


def test_commands_copied(installed):
    for f in (GLOBAL_SRC / "commands").iterdir():
        if f.is_file():
            assert (installed / "commands" / f.name).exists(), f"missing command: {f.name}"


def test_agents_copied(installed):
    for f in (GLOBAL_SRC / "agents").iterdir():
        if f.is_file():
            assert (installed / "agents" / f.name).exists(), f"missing agent: {f.name}"


def test_hooks_copied(installed):
    for f in (GLOBAL_SRC / "hooks").iterdir():
        if f.is_file():
            assert (installed / "hooks" / f.name).exists(), f"missing hook: {f.name}"


def test_settings_is_valid_json(installed):
    settings_path = installed / "settings.json"
    assert settings_path.exists()
    json.loads(settings_path.read_text())  # must not raise


def test_settings_contains_hooks(installed):
    installed_hooks = json.loads((installed / "settings.json").read_text()).get("hooks", {})
    src_hooks = json.loads((GLOBAL_SRC / "settings.json").read_text()).get("hooks", {})
    for event_type in src_hooks:
        assert event_type in installed_hooks, f"missing hook event: {event_type}"


def test_settings_contains_permissions(installed):
    installed_allow = (
        json.loads((installed / "settings.json").read_text())
        .get("permissions", {})
        .get("allow", [])
    )
    src_allow = (
        json.loads((GLOBAL_SRC / "settings.json").read_text())
        .get("permissions", {})
        .get("allow", [])
    )
    for entry in src_allow:
        assert entry in installed_allow, f"missing permission: {entry}"


def test_notes_vault_created(installed, fake_home):
    """upgrade() must create the notes vault directory tree under ~/.topgun.

    The slash command and topgun notes track depend on this directory
    existing. If it is absent, note creation silently fails or errors.
    """
    vault = fake_home / ".topgun" / "notes" / "obsidian-vault" / "topgun"
    assert vault.exists(), "notes vault directory not created by upgrade"


def test_notes_template_created(installed, fake_home):
    """upgrade() must write a default note.md template to _templates/.

    The /topgun-notes command reads this template before creating any
    note. A missing template causes the command to fall back to a
    hardcoded default, which is acceptable but not ideal — the template
    is the user's customisation point.
    """
    template = (
        fake_home / ".topgun" / "notes" / "obsidian-vault" / "topgun"
        / "_templates" / "note.md"
    )
    assert template.exists(), "_templates/note.md not created by upgrade"
    content = template.read_text()
    assert "{{title}}" in content
    assert "{{content}}" in content
