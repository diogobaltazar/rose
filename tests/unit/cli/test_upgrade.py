from topgun.cli.upgrade import _merge_permissions


def test_merge_permissions_into_empty():
    """_merge_permissions must add all source entries when destination has none.

    This is the primary installation path: a fresh ~/.claude/settings.json has
    no permissions key. Every curated entry must be written so the user benefits
    from the full allow-list on first upgrade.
    """
    src = {"permissions": {"allow": ["Bash(ls*)", "Bash(git log*)"]}}
    dest = {}
    changes = _merge_permissions(dest, src)
    assert dest["permissions"]["allow"] == ["Bash(ls*)", "Bash(git log*)"]
    assert len(changes) == 2


def test_merge_permissions_preserves_user_entries():
    """_merge_permissions must never remove entries the user has added.

    Users may add project-specific or personal permissions to their
    ~/.claude/settings.json. A topgun upgrade must not silently delete them,
    as this would break workflows the user has deliberately enabled.
    Edge cases not covered: duplicate user entries (preserved as-is).
    """
    src = {"permissions": {"allow": ["Bash(ls*)"]}}
    dest = {"permissions": {"allow": ["Bash(my-custom-script.sh*)"]}}
    _merge_permissions(dest, src)
    allow = dest["permissions"]["allow"]
    assert "Bash(my-custom-script.sh*)" in allow
    assert "Bash(ls*)" in allow


def test_merge_permissions_no_duplicates():
    """_merge_permissions must not add an entry that is already present.

    Running topgun upgrade is idempotent. If a permission is already in the
    destination allow-list — whether from a previous upgrade or added manually —
    it must not be duplicated. Duplicates in Claude Code's allow-list are
    harmless but produce a confusing settings file.
    """
    src = {"permissions": {"allow": ["Bash(ls*)", "Bash(git log*)"]}}
    dest = {"permissions": {"allow": ["Bash(ls*)"]}}
    changes = _merge_permissions(dest, src)
    assert dest["permissions"]["allow"].count("Bash(ls*)") == 1
    assert len(changes) == 1  # only git log* was added


def test_merge_permissions_idempotent():
    """_merge_permissions called twice must produce the same result as once.

    topgun upgrade may be run repeatedly. The second run must produce zero
    changes and must not alter the allow-list from what the first run produced.
    """
    src = {"permissions": {"allow": ["Bash(ls*)", "Bash(ps*)"]}}
    dest = {}
    _merge_permissions(dest, src)
    snapshot = list(dest["permissions"]["allow"])
    changes = _merge_permissions(dest, src)
    assert dest["permissions"]["allow"] == snapshot
    assert changes == []


def test_merge_permissions_empty_source():
    """_merge_permissions must be a no-op when the source has no permissions.

    If global/settings.json has no permissions key (e.g. during a transition),
    the function must not raise and must leave the destination unchanged.
    """
    src = {}
    dest = {"permissions": {"allow": ["Bash(ls*)"]}}
    changes = _merge_permissions(dest, src)
    assert dest["permissions"]["allow"] == ["Bash(ls*)"]
    assert changes == []
