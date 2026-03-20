"""
test_aq_backup_verify.py

Verifies that AQ21 and AQ22 have identical firmware and memory lists.

This test is the final safety check before a show — if it passes, both units
are in sync. Requires both AQ21 and AQ22 to be live on the network. See conftest.py.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))

from aquilon_comms import AquilonComms


@pytest.fixture(scope="module")
def primary_aq(primary_host, aq_port):
    aq = AquilonComms(host=primary_host, port=aq_port)
    try:
        aq.get_system_info()  # smoke test connectivity
    except ConnectionError as e:
        pytest.skip(f"AQ21 not reachable at {primary_host}: {e}")
    return aq


@pytest.fixture(scope="module")
def backup_aq(backup_host, aq_port):
    aq = AquilonComms(host=backup_host, port=aq_port)
    try:
        aq.get_system_info()  # smoke test connectivity
    except ConnectionError as e:
        pytest.skip(f"AQ22 not reachable at {backup_host}: {e}")
    return aq


@pytest.fixture(scope="module")
def primary_info(primary_aq):
    return primary_aq.get_system_info()


@pytest.fixture(scope="module")
def backup_info(backup_aq):
    return backup_aq.get_system_info()


@pytest.fixture(scope="module")
def primary_inputs(primary_aq):
    return {i["id"]: i for i in primary_aq.get_inputs()}


@pytest.fixture(scope="module")
def backup_inputs(backup_aq):
    return {i["id"]: i for i in backup_aq.get_inputs()}


@pytest.fixture(scope="module")
def primary_screens(primary_aq):
    return {s["id"]: s for s in primary_aq.get_screens()}


@pytest.fixture(scope="module")
def backup_screens(backup_aq):
    return {s["id"]: s for s in backup_aq.get_screens()}


@pytest.fixture(scope="module")
def primary_outputs(primary_aq):
    return {o.output_id: o for o in primary_aq.get_outputs()}


@pytest.fixture(scope="module")
def backup_outputs(backup_aq):
    return {o.output_id: o for o in backup_aq.get_outputs()}


@pytest.fixture(scope="module")
def primary_presets(primary_aq):
    return primary_aq.get_presets()


@pytest.fixture(scope="module")
def backup_presets(backup_aq):
    return backup_aq.get_presets()


# ---------------------------------------------------------------------------
# System info checks
# ---------------------------------------------------------------------------

def test_firmware_matches(primary_info, backup_info):
    """Both units must be running the same firmware version."""
    assert primary_info.get("firmware") == backup_info.get("firmware"), (
        f"Firmware mismatch: AQ21={primary_info.get('firmware')!r}, "
        f"AQ22={backup_info.get('firmware')!r}"
    )


def test_device_type_matches(primary_info, backup_info):
    """Both units must be the same device type."""
    assert primary_info.get("deviceType") == backup_info.get("deviceType"), (
        f"Device type mismatch: AQ21={primary_info.get('deviceType')!r}, "
        f"AQ22={backup_info.get('deviceType')!r}"
    )


# ---------------------------------------------------------------------------
# Input checks
# ---------------------------------------------------------------------------

def test_input_ids_match(primary_inputs, backup_inputs):
    assert set(primary_inputs) == set(backup_inputs), (
        f"Input ID sets differ — AQ21: {sorted(primary_inputs)}, AQ22: {sorted(backup_inputs)}"
    )


def test_input_labels_match(primary_inputs, backup_inputs):
    for input_id, pi in primary_inputs.items():
        bi = backup_inputs.get(input_id)
        if bi is None:
            continue
        assert pi.get("label") == bi.get("label"), (
            f"Input {input_id} label mismatch — AQ21: {pi.get('label')!r}, AQ22: {bi.get('label')!r}"
        )


# ---------------------------------------------------------------------------
# Screen checks
# ---------------------------------------------------------------------------

def test_screen_ids_match(primary_screens, backup_screens):
    assert set(primary_screens) == set(backup_screens), (
        f"Screen ID sets differ — AQ21: {sorted(primary_screens)}, AQ22: {sorted(backup_screens)}"
    )


def test_screen_labels_match(primary_screens, backup_screens):
    for screen_id, ps in primary_screens.items():
        bs = backup_screens.get(screen_id)
        if bs is None:
            continue
        assert ps.get("label") == bs.get("label"), (
            f"Screen {screen_id} label mismatch — AQ21: {ps.get('label')!r}, AQ22: {bs.get('label')!r}"
        )


def test_screen_enabled_state_matches(primary_screens, backup_screens):
    for screen_id, ps in primary_screens.items():
        bs = backup_screens.get(screen_id)
        if bs is None:
            continue
        assert ps.get("isEnabled") == bs.get("isEnabled"), (
            f"Screen {screen_id} isEnabled mismatch — AQ21: {ps.get('isEnabled')!r}, AQ22: {bs.get('isEnabled')!r}"
        )


# ---------------------------------------------------------------------------
# Output checks
# ---------------------------------------------------------------------------

def test_output_ids_match(primary_outputs, backup_outputs):
    assert set(primary_outputs) == set(backup_outputs), (
        f"Output ID sets differ — AQ21: {sorted(primary_outputs)}, AQ22: {sorted(backup_outputs)}"
    )


def test_output_labels_match(primary_outputs, backup_outputs):
    for out_id, po in primary_outputs.items():
        bo = backup_outputs.get(out_id)
        if bo is None:
            continue
        assert po.label == bo.label, (
            f"Output {out_id} label mismatch — AQ21: {po.label!r}, AQ22: {bo.label!r}"
        )


def test_output_formats_match(primary_outputs, backup_outputs):
    for out_id, po in primary_outputs.items():
        bo = backup_outputs.get(out_id)
        if bo is None:
            continue
        assert po.current_format == bo.current_format, (
            f"Output {out_id} format mismatch — AQ21: {po.current_format!r}, AQ22: {bo.current_format!r}"
        )


# ---------------------------------------------------------------------------
# Preset / memory checks
# ---------------------------------------------------------------------------

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
            continue  # caught by previous test
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
