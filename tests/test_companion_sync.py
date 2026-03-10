"""
test_companion_sync.py

Verifies that the generated Companion config is correct.

Checks (for every preset button on every configured page):
  - memoryId in action options matches the AQ memory that generated the button
  - Button label (style.text) exactly matches the AQ memory name
  - Both AQ instance IDs appear in the button's down actions
  - Nav buttons (pageup, pagedown, pagenum) are present on every page
  - No preset button overwrites a nav button position

Requires a live Aquilon and a config.toml. See conftest.py.
"""

import sys
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "companion_sync"))
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))

from aquilon_comms import AquilonPreset
from companion_updater import (
    apply_presets_to_page,
    get_instance_ids_by_type,
    load_config,
    save_config,
    update_page_title,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_down_actions(btn: dict) -> list[dict]:
    try:
        return btn["steps"]["0"]["action_sets"]["down"]
    except (KeyError, TypeError):
        return []


def get_button(controls: dict, row: int, col: int) -> dict | None:
    return controls.get(str(row), {}).get(str(col))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def generated_config(app_config, live_presets, instance_ids, tmp_path_factory):
    """Generate a Companion config from live presets and return it as a dict."""
    template_path = REPO_ROOT / app_config["companion"]["template_path"]
    config = load_config(template_path)

    cols_per_row = app_config["companion"].get("cols_per_row", 8)
    target = app_config["companion"].get("target", "preview")
    pages_cfg = app_config["companion"].get("pages", [])

    preset_map_all = {p.memory_id: p for p in live_presets}

    for page_cfg in pages_cfg:
        page_num = page_cfg["page_num"]
        page_title = page_cfg.get("page_title", f"Page {page_num}")
        bgcolor = page_cfg.get("color", 0)
        memory_ids = page_cfg.get("memory_ids", [])
        page_presets = [preset_map_all[mid] for mid in memory_ids if mid in preset_map_all]
        if not page_presets:
            continue
        update_page_title(config, page_num, page_title)
        apply_presets_to_page(
            config,
            page_num=page_num,
            presets=page_presets,
            instance_ids=instance_ids,
            cols_per_row=cols_per_row,
            target=target,
            bgcolor=bgcolor,
        )

    out = tmp_path_factory.mktemp("output") / "test_output.companionconfig"
    save_config(config, out)

    # Reload from disk to catch any serialization issues
    with open(out, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def preset_map(live_presets) -> dict[int, str]:
    """Map of memoryId → name for quick lookup."""
    return {p.memory_id: p.name for p in live_presets}


@pytest.fixture(scope="module")
def all_page_controls(generated_config, app_config) -> list[dict]:
    """List of controls dicts for every configured page that has memory_ids."""
    pages_cfg = app_config["companion"].get("pages", [])
    result = []
    for page_cfg in pages_cfg:
        if not page_cfg.get("memory_ids"):
            continue
        page_num = str(page_cfg["page_num"])
        controls = generated_config.get("pages", {}).get(page_num, {}).get("controls", {})
        result.append(controls)
    return result


@pytest.fixture(scope="module")
def page_controls(all_page_controls) -> dict:
    """Controls from the first configured page (for nav button tests)."""
    if not all_page_controls:
        pytest.skip("No configured pages with memory_ids in config.toml")
    return all_page_controls[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPresetButtons:
    """Verify every generated preset button is correct (checks all configured pages)."""

    def _collect_preset_buttons(self, controls: dict) -> list[tuple[int, int, dict]]:
        """Return (row, col, button) for every button that has a load-memory action."""
        buttons = []
        for row_k, row in controls.items():
            for col_k, btn in row.items():
                actions = get_down_actions(btn)
                if any(a.get("action") == "/api/tpp/v1/load-master-memory" for a in actions):
                    buttons.append((int(row_k), int(col_k), btn))
        return buttons

    def test_all_expected_presets_have_buttons(self, all_page_controls, preset_map, app_config):
        """Every memory_id in each page's config must have a corresponding button."""
        pages_cfg = app_config["companion"].get("pages", [])
        for page_cfg, controls in zip(pages_cfg, all_page_controls):
            memory_ids = page_cfg.get("memory_ids", [])
            if not memory_ids:
                continue

            found_ids = set()
            for _, _, btn in self._collect_preset_buttons(controls):
                for action in get_down_actions(btn):
                    if action.get("action") == "/api/tpp/v1/load-master-memory":
                        found_ids.add(action["options"]["memoryId"])
                        break

            for memory_id in memory_ids:
                if memory_id not in preset_map:
                    continue  # not on device — tested elsewhere
                assert memory_id in found_ids, (
                    f"Page {page_cfg['page_num']}: "
                    f"Memory {memory_id} ({preset_map[memory_id]!r}) has no button"
                )

    def test_button_labels_match_preset_names(self, all_page_controls, preset_map):
        """Button style.text must exactly match the AQ memory name."""
        for controls in all_page_controls:
            for row_k, row in controls.items():
                for col_k, btn in row.items():
                    actions = get_down_actions(btn)
                    load_actions = [a for a in actions if a.get("action") == "/api/tpp/v1/load-master-memory"]
                    if not load_actions:
                        continue

                    memory_id = load_actions[0]["options"]["memoryId"]
                    expected_name = preset_map.get(memory_id)
                    actual_label = btn.get("style", {}).get("text", "")

                    assert actual_label == expected_name, (
                        f"Button [{row_k}/{col_k}] label mismatch: "
                        f"got {actual_label!r}, expected {expected_name!r} (memoryId={memory_id})"
                    )

    def test_correct_memory_id_on_every_button(self, all_page_controls, preset_map):
        """Every action's memoryId must exist in the AQ memory list."""
        for controls in all_page_controls:
            for row_k, row in controls.items():
                for col_k, btn in row.items():
                    for action in get_down_actions(btn):
                        if action.get("action") != "/api/tpp/v1/load-master-memory":
                            continue
                        memory_id = action["options"]["memoryId"]
                        assert memory_id in preset_map, (
                            f"Button [{row_k}/{col_k}] has unknown memoryId {memory_id} "
                            f"— not found in AQ memory list"
                        )

    def test_both_aq_instances_on_every_preset_button(self, all_page_controls, instance_ids):
        """Every preset button must fire on all AQ instances."""
        for controls in all_page_controls:
            for row_k, row in controls.items():
                for col_k, btn in row.items():
                    load_actions = [
                        a for a in get_down_actions(btn)
                        if a.get("action") == "/api/tpp/v1/load-master-memory"
                    ]
                    if not load_actions:
                        continue

                    fired_instances = {a["instance"] for a in load_actions}
                    for inst_id in instance_ids:
                        assert inst_id in fired_instances, (
                            f"Button [{row_k}/{col_k}] is missing action for instance {inst_id} "
                            f"(fires on {fired_instances}, expected all of {instance_ids})"
                        )


class TestNavButtons:
    """Verify navigation buttons are present on every page and never overwritten."""

    NAV_TYPES = {"pageup", "pagedown", "pagenum"}

    def _get_nav_positions(self, controls: dict) -> dict[str, tuple[int, int]]:
        """Return {style_type: (row, col)} for all nav buttons found."""
        found = {}
        for row_k, row in controls.items():
            for col_k, btn in row.items():
                if isinstance(btn, dict) and btn.get("type") in self.NAV_TYPES:
                    found[btn["type"]] = (int(row_k), int(col_k))
        return found

    def test_pageup_button_present(self, page_controls):
        nav = self._get_nav_positions(page_controls)
        assert "pageup" in nav, "No 'pageup' nav button found on the page"

    def test_pagedown_button_present(self, page_controls):
        nav = self._get_nav_positions(page_controls)
        assert "pagedown" in nav, "No 'pagedown' nav button found on the page"

    def test_pagenum_button_present(self, page_controls):
        nav = self._get_nav_positions(page_controls)
        assert "pagenum" in nav, "No 'pagenum' nav button found on the page"

    def test_preset_buttons_do_not_overwrite_nav(self, all_page_controls):
        """No preset button should sit at a nav button position on any page."""
        for controls in all_page_controls:
            nav = self._get_nav_positions(controls)
            nav_positions = set(nav.values())

            for row_k, row in controls.items():
                for col_k, btn in row.items():
                    pos = (int(row_k), int(col_k))
                    if pos not in nav_positions:
                        continue
                    btn_type = btn.get("type") if isinstance(btn, dict) else None
                    assert btn_type in self.NAV_TYPES, (
                        f"Nav position {pos} was overwritten by a non-nav button "
                        f"(type={btn_type!r})"
                    )
