"""
test_companion_updater.py

Offline unit tests for companion_updater.py — no live AQ required.

Covers:
  - Smart text sizing (_wrap_lines, smart_text_size)
  - build_preset_button structure and instance wiring
  - build_screen_take_button / build_label_button
  - apply_presets_to_page  (nav safety, clear_first, pinned_positions)
  - place_preset_button    (nav guard, placement)
  - place_template_button  (screen-take, label, nav guard, unknown action)
  - get_instance_ids_by_type
  - update_page_title
  - main.py --config CLI argument
"""

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "companion_sync"))
sys.path.insert(0, str(REPO_ROOT / "src" / "common"))

from aquilon_comms import AquilonPreset
from companion_updater import (
    NAV_POSITIONS,
    CHARS_PER_LINE,
    MAX_LINES,
    FONT_SIZES,
    _wrap_lines,
    _line_count,
    _has_mid_word_wrap,
    _fits,
    smart_text_size,
    build_preset_button,
    build_screen_take_button,
    build_label_button,
    build_page_jump_button,
    apply_presets_to_page,
    place_preset_button,
    place_template_button,
    get_instance_ids_by_type,
    update_page_title,
)


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

def make_preset(memory_id: int = 1, name: str = "Test Preset") -> AquilonPreset:
    return AquilonPreset(memory_id=memory_id, name=name)


def make_config(pages: list[int] | None = None) -> dict:
    """Minimal Companion config dict with the given page numbers."""
    pages = pages or [1]
    return {
        "version": 6,
        "instances": {},
        "pages": {
            str(p): {
                "name": f"Page {p}",
                "controls": {},
            }
            for p in pages
        },
    }


def get_down_actions(btn: dict) -> list[dict]:
    try:
        return btn["steps"]["0"]["action_sets"]["down"]
    except (KeyError, TypeError):
        return []


# ---------------------------------------------------------------------------
# Smart text sizing
# ---------------------------------------------------------------------------

class TestWrapLines:
    def test_single_short_word(self):
        assert _wrap_lines("Hello", 10) == ["Hello"]

    def test_two_words_fit_on_one_line(self):
        assert _wrap_lines("Hi there", 10) == ["Hi there"]

    def test_two_words_split_to_two_lines(self):
        lines = _wrap_lines("Hello World", 5)
        assert lines == ["Hello", "World"]

    def test_empty_string(self):
        assert _wrap_lines("", 10) == [""]

    def test_word_longer_than_limit_occupies_own_line(self):
        # "SUPERLONGWORD" is 13 chars — longer than limit of 5
        lines = _wrap_lines("SUPERLONGWORD next", 5)
        assert lines[0] == "SUPERLONGWORD"
        assert lines[1] == "next"


class TestSmartTextSize:
    def test_short_label_returns_auto(self):
        # Very short labels fit at the largest size — no override needed
        result = smart_text_size("Hi", "auto")
        assert result == "auto"

    def test_explicit_size_passes_through_unchanged(self):
        assert smart_text_size("Any Label Text Here", "14") == "14"
        assert smart_text_size("Short", "30") == "30"

    def test_long_label_steps_down_from_auto(self):
        # A label that won't fit at size 30 should get a smaller size
        long_label = "Pyramid Stage Saturday Night"
        result = smart_text_size(long_label, "auto")
        # Result must be a valid size or "auto"
        assert result in FONT_SIZES + ["auto"]
        # And it should not be 30 (too large for this text)
        if result != "auto":
            assert result != "30"

    def test_very_long_single_word_returns_valid_size(self):
        # A single word too long to ever wrap cleanly should still return something valid
        result = smart_text_size("SUPERLONGWORDTHATCANNOTFIT", "auto")
        assert result in FONT_SIZES + ["auto"]


class TestLineCount:
    def test_one_line(self):
        assert _line_count("Hello", 10) == 1

    def test_two_lines(self):
        assert _line_count("Hello World", 5) == 2


class TestHasMidWordWrap:
    def test_no_long_words(self):
        assert not _has_mid_word_wrap("Short words", 7)

    def test_long_word_triggers(self):
        assert _has_mid_word_wrap("SUPERLONGWORD", 5)


# ---------------------------------------------------------------------------
# Button builders
# ---------------------------------------------------------------------------

class TestBuildPresetButton:
    def test_structure(self):
        preset = make_preset(42, "Main Stage")
        btn = build_preset_button(preset, ["inst1"])
        assert btn["type"] == "button"
        assert "style" in btn
        assert "steps" in btn

    def test_label_from_preset_name(self):
        preset = make_preset(1, "My Preset")
        btn = build_preset_button(preset, ["inst1"])
        assert btn["style"]["text"] == "My Preset"

    def test_explicit_label_overrides_preset_name(self):
        preset = make_preset(1, "My Preset")
        btn = build_preset_button(preset, ["inst1"], label="Custom Label")
        assert btn["style"]["text"] == "Custom Label"

    def test_action_count_matches_instance_count(self):
        preset = make_preset(5, "Foo")
        btn = build_preset_button(preset, ["inst1", "inst2", "inst3"])
        actions = get_down_actions(btn)
        assert len(actions) == 3

    def test_action_uses_correct_memory_id(self):
        preset = make_preset(99, "Bar")
        btn = build_preset_button(preset, ["inst1"])
        action = get_down_actions(btn)[0]
        assert action["options"]["memoryId"] == 99

    def test_action_uses_correct_instance(self):
        preset = make_preset(1, "Baz")
        btn = build_preset_button(preset, ["aq21_id", "aq22_id"])
        actions = get_down_actions(btn)
        instances = {a["connectionId"] for a in actions}
        assert instances == {"aq21_id", "aq22_id"}

    def test_target_default_preview(self):
        preset = make_preset(1, "X")
        btn = build_preset_button(preset, ["inst1"])
        assert get_down_actions(btn)[0]["options"]["target"] == "preview"

    def test_target_program(self):
        preset = make_preset(1, "X")
        btn = build_preset_button(preset, ["inst1"], target="program")
        assert get_down_actions(btn)[0]["options"]["target"] == "program"

    def test_bgcolor_applied(self):
        preset = make_preset(1, "X")
        btn = build_preset_button(preset, ["inst1"], bgcolor=0x003300)
        assert btn["style"]["bgcolor"] == 0x003300

    def test_text_color_applied(self):
        preset = make_preset(1, "X")
        btn = build_preset_button(preset, ["inst1"], text_color=0xFF0000)
        assert btn["style"]["color"] == 0xFF0000

    def test_action_ids_are_unique(self):
        preset = make_preset(1, "X")
        btn = build_preset_button(preset, ["inst1", "inst2"])
        ids = [a["id"] for a in get_down_actions(btn)]
        assert len(ids) == len(set(ids))


class TestBuildPageJumpButton:
    def test_structure(self):
        btn = build_page_jump_button(40, label="MV Router")
        assert btn["type"] == "button"
        assert btn["style"]["text"] == "MV Router"

    def test_action_is_set_page(self):
        btn = build_page_jump_button(40)
        action = get_down_actions(btn)[0]
        assert action["definitionId"] == "set_page"
        assert action["connectionId"] == "internal"
        assert action["type"] == "action"
        assert action["children"] == {}

    def test_target_page_in_options(self):
        btn = build_page_jump_button(99)
        assert get_down_actions(btn)[0]["options"]["page"] == 99

    def test_static_controller(self):
        btn = build_page_jump_button(1, controller="streamdeck:ABC123")
        opts = get_down_actions(btn)[0]["options"]
        assert opts["controller_from_variable"] == False
        assert opts["controller"] == "streamdeck:ABC123"

    def test_variable_controller(self):
        btn = build_page_jump_button(1, controller="$(custom:green_surface)")
        opts = get_down_actions(btn)[0]["options"]
        assert opts["controller_from_variable"] == True
        assert opts["controller_variable"] == "$(custom:green_surface)"

    def test_default_controller_is_self(self):
        btn = build_page_jump_button(1)
        opts = get_down_actions(btn)[0]["options"]
        assert opts["controller_from_variable"] == False
        assert opts["controller"] == "self"

    def test_bgcolor_and_text_color(self):
        btn = build_page_jump_button(1, bgcolor=0x003300, text_color=0x6E6E6E)
        assert btn["style"]["bgcolor"] == 0x003300
        assert btn["style"]["color"] == 0x6E6E6E


class TestBuildScreenTakeButton:
    def test_structure(self):
        btn = build_screen_take_button(1, ["inst1"])
        assert btn["type"] == "button"
        assert btn["style"]["text"] == "TAKE"

    def test_action_type(self):
        btn = build_screen_take_button(1, ["inst1"])
        action = get_down_actions(btn)[0]
        assert "take" in action["definitionId"]

    def test_screen_id_in_action(self):
        btn = build_screen_take_button(2, ["inst1"])
        # action path contains the screen_id substituted or it's in options
        action = get_down_actions(btn)[0]
        assert action["options"]["screenId"] == 2

    def test_multiple_instances(self):
        btn = build_screen_take_button(1, ["inst1", "inst2"])
        assert len(get_down_actions(btn)) == 2


class TestBuildLabelButton:
    def test_no_down_actions(self):
        btn = build_label_button("Note")
        assert get_down_actions(btn) == []

    def test_label_in_style(self):
        btn = build_label_button("Important Note")
        assert btn["style"]["text"] == "Important Note"

    def test_show_topbar_default_false(self):
        btn = build_label_button("Note")
        assert btn["style"]["show_topbar"] == False


# ---------------------------------------------------------------------------
# apply_presets_to_page
# ---------------------------------------------------------------------------

class TestApplyPresetsToPage:
    def test_returns_count_of_stamped_buttons(self):
        config = make_config([1])
        presets = [make_preset(i, f"Preset {i}") for i in range(5)]
        n = apply_presets_to_page(config, 1, presets, ["inst1"])
        assert n == 5

    def test_buttons_land_in_correct_positions(self):
        config = make_config([1])
        presets = [make_preset(i, f"P{i}") for i in range(3)]
        apply_presets_to_page(config, 1, presets, ["inst1"], cols_per_row=8)
        controls = config["pages"]["1"]["controls"]
        assert "0" in controls and "0" in controls["0"]
        assert "0" in controls and "1" in controls["0"]
        assert "0" in controls and "2" in controls["0"]

    def test_nav_positions_are_never_overwritten(self):
        config = make_config([1])
        # Put nav stubs at the reserved positions
        for row, col in NAV_POSITIONS:
            config["pages"]["1"]["controls"].setdefault(str(row), {})[str(col)] = {"type": "pageup"}
        # Stamp enough presets to reach the nav zone
        presets = [make_preset(i, f"P{i}") for i in range(30)]
        apply_presets_to_page(config, 1, presets, ["inst1"], cols_per_row=8, clear_first=False)
        controls = config["pages"]["1"]["controls"]
        for row, col in NAV_POSITIONS:
            btn = controls.get(str(row), {}).get(str(col), {})
            assert btn.get("type") == "pageup", (
                f"Nav position ({row},{col}) was overwritten"
            )

    def test_clear_first_removes_old_buttons(self):
        config = make_config([1])
        config["pages"]["1"]["controls"]["0"] = {"0": {"type": "button", "style": {"text": "old"}}}
        apply_presets_to_page(config, 1, [make_preset(1, "New")], ["inst1"], clear_first=True)
        text = config["pages"]["1"]["controls"]["0"]["0"]["style"]["text"]
        assert text == "New"

    def test_clear_false_does_not_remove_nav(self):
        # clear_first=False should not wipe nav buttons that were already there
        config = make_config([1])
        nav_row, nav_col = list(NAV_POSITIONS)[0]
        config["pages"]["1"]["controls"].setdefault(str(nav_row), {})[str(nav_col)] = {"type": "pageup"}
        apply_presets_to_page(config, 1, [make_preset(1, "P1")], ["inst1"],
                               clear_first=False, cols_per_row=8)
        assert config["pages"]["1"]["controls"][str(nav_row)][str(nav_col)]["type"] == "pageup"

    def test_clear_false_overwrites_non_pinned_positions(self):
        # Without pinned_positions, auto-flow overwrites whatever is in the slot
        config = make_config([1])
        existing = {"type": "button", "style": {"text": "old"}}
        config["pages"]["1"]["controls"]["0"] = {"0": existing}
        apply_presets_to_page(config, 1, [make_preset(99, "New")], ["inst1"],
                               clear_first=False, cols_per_row=8)
        assert config["pages"]["1"]["controls"]["0"]["0"]["style"]["text"] == "New"

    def test_pinned_positions_are_skipped(self):
        config = make_config([1])
        pinned = frozenset([(0, 0), (0, 1)])
        presets = [make_preset(1, "First")]
        apply_presets_to_page(config, 1, presets, ["inst1"],
                               pinned_positions=pinned, clear_first=True)
        controls = config["pages"]["1"]["controls"]
        # First available slot after (0,0) and (0,1) should be (0,2)
        assert "2" in controls.get("0", {}), "Button should be at (0,2), skipping pinned (0,0) and (0,1)"

    def test_empty_presets_stamps_nothing(self):
        config = make_config([1])
        n = apply_presets_to_page(config, 1, [], ["inst1"])
        assert n == 0


# ---------------------------------------------------------------------------
# place_preset_button
# ---------------------------------------------------------------------------

class TestPlacePresetButton:
    def test_places_button_at_position(self):
        config = make_config([1])
        place_preset_button(config, 1, 0, 0, make_preset(7, "Foo"), ["inst1"])
        assert config["pages"]["1"]["controls"]["0"]["0"]["style"]["text"] == "Foo"

    def test_raises_on_nav_position(self):
        config = make_config([1])
        for row, col in NAV_POSITIONS:
            with pytest.raises(ValueError, match="reserved nav position"):
                place_preset_button(config, 1, row, col, make_preset(1, "X"), ["inst1"])

    def test_custom_label(self):
        config = make_config([1])
        place_preset_button(config, 1, 0, 0, make_preset(1, "Device Name"), ["inst1"],
                            label="Override")
        assert config["pages"]["1"]["controls"]["0"]["0"]["style"]["text"] == "Override"


# ---------------------------------------------------------------------------
# place_template_button
# ---------------------------------------------------------------------------

class TestPlaceTemplateButton:
    def test_screen_take_button(self):
        config = make_config([1])
        template = {"action": "screen-take", "screen_id": 1, "label": "TAKE"}
        place_template_button(config, 1, 0, 0, template, ["inst1"])
        btn = config["pages"]["1"]["controls"]["0"]["0"]
        assert btn["style"]["text"] == "TAKE"
        action = get_down_actions(btn)[0]
        assert "take" in action["definitionId"]

    def test_label_button(self):
        config = make_config([1])
        template = {"action": "label", "label": "NOTE: check camera"}
        place_template_button(config, 1, 0, 0, template, ["inst1"])
        btn = config["pages"]["1"]["controls"]["0"]["0"]
        assert btn["style"]["text"] == "NOTE: check camera"
        assert get_down_actions(btn) == []

    def test_page_jump_button(self):
        config = make_config([1])
        template = {"action": "page-jump", "page": 40, "label": "MV Router", "color": 0x003300}
        place_template_button(config, 1, 0, 0, template, ["inst1"])
        btn = config["pages"]["1"]["controls"]["0"]["0"]
        assert btn["style"]["text"] == "MV Router"
        assert get_down_actions(btn)[0]["definitionId"] == "set_page"
        assert get_down_actions(btn)[0]["options"]["page"] == 40

    def test_page_jump_variable_controller(self):
        config = make_config([1])
        template = {"action": "page-jump", "page": 1, "label": "Day 1",
                    "controller": "$(custom:green_surface)"}
        place_template_button(config, 1, 0, 0, template, ["inst1"])
        opts = get_down_actions(config["pages"]["1"]["controls"]["0"]["0"])[0]["options"]
        assert opts["controller_from_variable"] == True
        assert opts["controller_variable"] == "$(custom:green_surface)"

    def test_raises_on_unknown_action(self):
        config = make_config([1])
        with pytest.raises(ValueError, match="Unknown template action"):
            place_template_button(config, 1, 0, 0, {"action": "bogus"}, ["inst1"])

    def test_raises_on_nav_position(self):
        config = make_config([1])
        for row, col in NAV_POSITIONS:
            with pytest.raises(ValueError, match="reserved nav position"):
                place_template_button(config, 1, row, col,
                                      {"action": "screen-take", "screen_id": 1}, ["inst1"])


# ---------------------------------------------------------------------------
# get_instance_ids_by_type
# ---------------------------------------------------------------------------

class TestGetInstanceIdsByType:
    def test_returns_matching_instances(self):
        config = {
            "instances": {
                "abc123": {"instance_type": "analogway-livepremier", "enabled": True, "sortOrder": 1},
                "def456": {"instance_type": "analogway-livepremier", "enabled": True, "sortOrder": 2},
                "zzz999": {"instance_type": "other-module", "enabled": True, "sortOrder": 0},
            }
        }
        ids = get_instance_ids_by_type(config, "analogway-livepremier")
        assert "abc123" in ids
        assert "def456" in ids
        assert "zzz999" not in ids

    def test_sorted_by_sort_order(self):
        config = {
            "instances": {
                "second": {"instance_type": "analogway-livepremier", "enabled": True, "sortOrder": 2},
                "first":  {"instance_type": "analogway-livepremier", "enabled": True, "sortOrder": 1},
            }
        }
        ids = get_instance_ids_by_type(config, "analogway-livepremier")
        assert ids == ["first", "second"]

    def test_disabled_instances_excluded(self):
        config = {
            "instances": {
                "active":   {"instance_type": "analogway-livepremier", "enabled": True,  "sortOrder": 1},
                "inactive": {"instance_type": "analogway-livepremier", "enabled": False, "sortOrder": 2},
            }
        }
        ids = get_instance_ids_by_type(config, "analogway-livepremier")
        assert "active" in ids
        assert "inactive" not in ids

    def test_no_matches_returns_empty(self):
        config = {"instances": {"xyz": {"instance_type": "other", "enabled": True}}}
        assert get_instance_ids_by_type(config, "analogway-livepremier") == []

    def test_empty_instances_returns_empty(self):
        assert get_instance_ids_by_type({}, "analogway-livepremier") == []


# ---------------------------------------------------------------------------
# update_page_title
# ---------------------------------------------------------------------------

class TestUpdatePageTitle:
    def test_sets_page_name(self):
        config = make_config([1])
        update_page_title(config, 1, "My Show")
        assert config["pages"]["1"]["name"] == "My Show"

    def test_accepts_string_page_num(self):
        config = make_config([2])
        update_page_title(config, "2", "Day Two")
        assert config["pages"]["2"]["name"] == "Day Two"

    def test_missing_page_does_not_raise(self):
        config = make_config([1])
        # Page 99 doesn't exist — should log a warning but not crash
        update_page_title(config, 99, "Ghost Page")


# ---------------------------------------------------------------------------
# CLI --config argument
# ---------------------------------------------------------------------------

class TestMainArgParsing:
    def test_default_config_is_config_toml(self):
        sys.path.insert(0, str(REPO_ROOT / "src" / "companion_sync"))
        from main import parse_args
        args = parse_args.__wrapped__() if hasattr(parse_args, "__wrapped__") else None
        # Call parse_args with no argv — argparse reads sys.argv[1:]
        import sys as _sys
        old = _sys.argv
        try:
            _sys.argv = ["main.py"]
            args = parse_args()
        finally:
            _sys.argv = old
        assert args.config.name == "config.toml"

    def test_custom_config_path(self):
        from main import parse_args
        import sys as _sys
        old = _sys.argv
        try:
            _sys.argv = ["main.py", "--config", "my_show_config.toml"]
            args = parse_args()
        finally:
            _sys.argv = old
        assert args.config == Path("my_show_config.toml")

    def test_short_flag(self):
        from main import parse_args
        import sys as _sys
        old = _sys.argv
        try:
            _sys.argv = ["main.py", "-c", "my_config.toml"]
            args = parse_args()
        finally:
            _sys.argv = old
        assert args.config == Path("my_config.toml")
