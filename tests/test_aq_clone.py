"""
test_aq_clone.py

Verifies that AQ21 and AQ22 have identical memory lists.

This test is the final safety check before a show — if it passes, both units
are in sync. If it fails, the clone did not complete successfully.

Requires both AQ21 and AQ22 to be live on the network. See conftest.py.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))

from aquilon_comms import AquilonComms


@pytest.fixture(scope="module")
def primary_presets(primary_host, aq_port):
    """Presets from AQ21 (primary)."""
    aq = AquilonComms(host=primary_host, port=aq_port)
    try:
        return aq.get_presets()
    except ConnectionError as e:
        pytest.skip(f"AQ21 not reachable at {primary_host}: {e}")


@pytest.fixture(scope="module")
def backup_presets(backup_host, aq_port):
    """Presets from AQ22 (backup)."""
    aq = AquilonComms(host=backup_host, port=aq_port)
    try:
        return aq.get_presets()
    except ConnectionError as e:
        pytest.skip(f"AQ22 not reachable at {backup_host}: {e}")


def test_both_units_have_same_preset_count(primary_presets, backup_presets):
    """AQ21 and AQ22 must have the same number of memories."""
    assert len(primary_presets) == len(backup_presets), (
        f"Memory count mismatch: AQ21 has {len(primary_presets)}, "
        f"AQ22 has {len(backup_presets)}"
    )


def test_all_primary_memories_exist_on_backup(primary_presets, backup_presets):
    """Every memory on AQ21 must exist on AQ22 with the same ID."""
    backup_ids = {p.memory_id for p in backup_presets}
    for p in primary_presets:
        assert p.memory_id in backup_ids, (
            f"Memory {p.memory_id} ({p.name!r}) is on AQ21 but missing from AQ22"
        )


def test_all_primary_memory_names_match_backup(primary_presets, backup_presets):
    """Every memory name on AQ21 must exactly match the same ID on AQ22."""
    backup_map = {p.memory_id: p.name for p in backup_presets}
    for p in primary_presets:
        if p.memory_id not in backup_map:
            continue  # caught by the previous test
        assert backup_map[p.memory_id] == p.name, (
            f"Name mismatch for memory {p.memory_id}: "
            f"AQ21={p.name!r}, AQ22={backup_map[p.memory_id]!r}"
        )


def test_no_extra_memories_on_backup(primary_presets, backup_presets):
    """AQ22 must not have memories that AQ21 does not have."""
    primary_ids = {p.memory_id for p in primary_presets}
    for p in backup_presets:
        assert p.memory_id in primary_ids, (
            f"Memory {p.memory_id} ({p.name!r}) is on AQ22 but not on AQ21"
        )
