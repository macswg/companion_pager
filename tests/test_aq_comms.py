"""
test_aq_comms.py

Verifies that the AquilonComms client correctly connects to the live Aquilon
and returns a usable preset list.

Requires a live Aquilon. See conftest.py.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))

from aquilon_comms import AquilonComms, AquilonPreset


def test_get_presets_returns_list(live_presets):
    """get_presets() must return a non-empty list."""
    assert isinstance(live_presets, list), "Expected a list of presets"
    assert len(live_presets) > 0, "Preset list is empty — nothing to put on buttons"


def test_presets_are_correct_type(live_presets):
    """Every item in the list must be an AquilonPreset."""
    for p in live_presets:
        assert isinstance(p, AquilonPreset), f"Expected AquilonPreset, got {type(p)}"


def test_all_presets_have_integer_ids(live_presets):
    """Every preset must have an integer memory_id."""
    for p in live_presets:
        assert isinstance(p.memory_id, int), (
            f"Preset {p!r} has non-integer memory_id: {p.memory_id!r}"
        )


def test_all_presets_have_non_empty_names(live_presets):
    """Every preset must have a non-empty name string."""
    for p in live_presets:
        assert isinstance(p.name, str) and p.name.strip(), (
            f"Preset with memory_id={p.memory_id} has empty or missing name"
        )


def test_preset_ids_are_unique(live_presets):
    """No two presets should share a memory_id."""
    ids = [p.memory_id for p in live_presets]
    assert len(ids) == len(set(ids)), (
        f"Duplicate memory IDs found: "
        f"{[i for i in ids if ids.count(i) > 1]}"
    )


def test_presets_are_sorted_by_id(live_presets):
    """Presets should come back sorted ascending by memory_id."""
    ids = [p.memory_id for p in live_presets]
    assert ids == sorted(ids), "Presets are not sorted by memory_id"


def test_connection_error_on_bad_host():
    """A bad host must raise ConnectionError, not hang or crash silently."""
    aq = AquilonComms(host="192.0.2.1", port=9999)  # TEST-NET — guaranteed unreachable
    with pytest.raises(ConnectionError):
        aq.get_presets()
