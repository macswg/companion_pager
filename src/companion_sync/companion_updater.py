#!/usr/bin/env python3
"""
companion_updater.py

Reads a Companion v6 config file (YAML), updates button titles and action
memoryIds to match Aquilon (Analog Way LivePremier) preset names and indexes,
and writes the result back as YAML.

Companion v6 stores configs as YAML. Each button's action uses:
  action: /api/tpp/v1/load-master-memory
  options:
    memoryId: <int>     ← preset index
    target: preview     ← or "program"

When both AQ21 and AQ22 are configured, the same action appears twice in the
button's "down" list — once per instance. This module handles that by updating
all actions matching the target action name.
"""

import copy
import logging
import math
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is required. Install it with: pip install pyyaml"
    )

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonPreset

logger = logging.getLogger(__name__)

LOAD_MEMORY_ACTION = "/api/tpp/v1/load-master-memory"
SCREEN_TAKE_ACTION = "/api/tpp/v1/screens/{screenId}/take"

# Font sizes available in Companion, largest to smallest.
FONT_SIZES: list[str] = ["30", "24", "18", "14", "7"]

# Estimated maximum characters per line at each font size on a 96x96 Stream Deck XL button.
# Tune these values against the tablet view (127.0.0.1:8888/tablet) if wrapping is off.
CHARS_PER_LINE: dict[str, int] = {
    "30": 5,
    "24": 5,
    "18": 7,
    "14": 12,
    "7":  17,
}

# Maximum lines visible on a 96x96 Stream Deck XL button at each font size.
# Tune against the tablet view (127.0.0.1:8888/tablet) if sizing is off.
MAX_LINES: dict[str, int] = {
    "30": 2,
    "24": 2,
    "18": 2,
    "14": 4,
    "7":  8,
}

# Nav button positions on a Stream Deck XL (row, col) — must never be overwritten.
# Confirmed from reference config: pageup=row2/col7, pagenum=row3/col6, pagedown=row3/col7.
NAV_POSITIONS: frozenset[tuple[int, int]] = frozenset({
    (2, 7),  # pageup
    (3, 6),  # pagenum
    (3, 7),  # pagedown
})


# ---------------------------------------------------------------------------
# Smart text sizing
# ---------------------------------------------------------------------------

def _wrap_lines(text: str, chars_per_line: int) -> list[str]:
    """
    Word-wrap text at chars_per_line, splitting at space boundaries.

    Simulates Companion's word-wrap behaviour: words are placed on a line
    until the next word would exceed chars_per_line, then a new line starts.
    A word longer than chars_per_line cannot be avoided and occupies its own
    line (causing a visual truncation / overflow).
    """
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= chars_per_line:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _line_count(text: str, chars_per_line: int) -> int:
    """Number of lines after word-wrapping text at chars_per_line."""
    return len(_wrap_lines(text, chars_per_line))


def _has_mid_word_wrap(text: str, chars_per_line: int) -> bool:
    """
    Return True if word-wrapping would still split a word.

    With proper word-wrap, a mid-word break only occurs when a single word
    is longer than chars_per_line (it cannot fit on any line without breaking).
    """
    return any(len(word) > chars_per_line for word in text.split())


def _fits(text: str, size: str) -> bool:
    """Return True if text fits within the line capacity for the given size."""
    cpl = CHARS_PER_LINE[size]
    return (
        _line_count(text, cpl) <= MAX_LINES[size]
        and not _has_mid_word_wrap(text, cpl)
    )


def _resolve_auto_size(text: str) -> str:
    """
    Estimate the font size Companion's 'auto' would select for this text.

    Picks the largest size where the word-wrapped line count fits within
    the button's visible line capacity for that size.
    """
    for size in FONT_SIZES:
        if _line_count(text, CHARS_PER_LINE[size]) <= MAX_LINES[size]:
            return size
    return FONT_SIZES[-1]


def smart_text_size(label: str, requested_size: str = "auto") -> str:
    """
    Return the appropriate font size for this label.

    Only acts on "auto" buttons — explicit sizes (e.g. "14") are always
    returned unchanged, trusting the user's manual choice.

    For "auto" buttons:
      - Estimates the size Companion would pick, then steps down if that size
        causes a mid-word break or line overflow.
      - If the auto-resolved size already fits cleanly, returns "auto" so
        Companion handles rendering natively.
      - If no size avoids a mid-word break (e.g. a single very long word),
        falls back to the largest size that at least fits within line capacity.

    Tune CHARS_PER_LINE and MAX_LINES at the top of this file against the
    tablet view (127.0.0.1:8888/tablet) if sizing is off.
    """
    if requested_size != "auto":
        return requested_size  # always respect explicit sizes

    # If the text fits cleanly at the largest size, Companion's native "auto"
    # will pick the right size on its own — no override needed.
    if _fits(label, FONT_SIZES[0]):
        return "auto"

    start = _resolve_auto_size(label)

    try:
        idx = FONT_SIZES.index(start)
    except ValueError:
        return "auto"

    # Step down until a size fits cleanly.
    for size in FONT_SIZES[idx:]:
        if _fits(label, size):
            return size

    # Fallback: word is too long to avoid breaking at any size — pick the
    # largest size that at least fits within the button's line capacity.
    for size in FONT_SIZES[idx:]:
        if _line_count(label, CHARS_PER_LINE[size]) <= MAX_LINES[size]:
            return size

    return FONT_SIZES[-1]


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def load_config(path: str | Path) -> dict:
    """Load a Companion v6 YAML config file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    logger.debug(f"Loaded config from {path} (version: {data.get('version')})")
    return data


def save_config(data: dict, path: str | Path) -> None:
    """Write the updated config as YAML."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    logger.info(f"Saved updated config to {path}")


# ---------------------------------------------------------------------------
# Page helpers
# ---------------------------------------------------------------------------

def update_page_title(config: dict, page_num: str | int, title: str) -> None:
    """Set the name of a Companion page."""
    page_num = str(page_num)
    try:
        config["pages"][page_num]["name"] = title
        logger.debug(f"Set page {page_num} title to {title!r}")
    except KeyError as e:
        logger.warning(f"Could not set page title for page {page_num} — missing key: {e}")


def clear_page_buttons(config: dict, page_num: str | int) -> None:
    """Remove all button controls from a page."""
    page_num = str(page_num)
    config["pages"][page_num]["controls"] = {}
    logger.debug(f"Cleared all buttons on page {page_num}")


# ---------------------------------------------------------------------------
# Button building
# ---------------------------------------------------------------------------

def _new_action_id() -> str:
    """Generate a unique action ID string (Companion format: 22-char base64-ish)."""
    return str(uuid.uuid4()).replace("-", "")[:22]


def build_preset_button(
    preset: AquilonPreset,
    instance_ids: list[str],
    target: str = "preview",
    text_size: str = "auto",
    text_color: int = 16777215,   # white
    bgcolor: int = 0,             # black
    smart_wrap: bool = False,
    label: str | None = None,
) -> dict:
    """
    Build a Companion v6 button dict for a single Aquilon preset.

    The button fires /api/tpp/v1/load-master-memory on every provided
    instance (one action entry per instance, in a single "down" list).

    Args:
        preset:        The AquilonPreset to represent.
        instance_ids:  List of Companion instance IDs (one per Aquilon unit).
        target:        "preview" or "program".
        text_size:     Font size string (e.g. "18", "auto").
        text_color:    Foreground color as a 24-bit int.
        bgcolor:       Background color as a 24-bit int.

    Returns:
        Dict matching the Companion v6 button schema.
    """
    display_label = label if label is not None else preset.name
    resolved_size = smart_text_size(display_label, text_size) if smart_wrap else text_size

    down_actions = [
        {
            "id": _new_action_id(),
            "type": "action",
            "definitionId": LOAD_MEMORY_ACTION,
            "connectionId": inst_id,
            "options": {
                "memoryId": preset.memory_id,
                "target": target,
            },
        }
        for inst_id in instance_ids
    ]

    return {
        "type": "button",
        "style": {
            "text": display_label,
            "textExpression": False,
            "size": resolved_size,
            "png64": None,
            "alignment": "center:center",
            "pngalignment": "center:center",
            "color": text_color,
            "bgcolor": bgcolor,
            "show_topbar": "default",
        },
        "options": {
            "rotaryActions": False,
            "stepAutoProgress": True,
        },
        "feedbacks": [],
        "steps": {
            "0": {
                "action_sets": {
                    "down": down_actions,
                    "up": [],
                },
                "options": {
                    "runWhileHeld": [],
                },
            }
        },
    }


# ---------------------------------------------------------------------------
# Page population
# ---------------------------------------------------------------------------

def place_preset_button(
    config: dict,
    page_num: str | int,
    row: int,
    col: int,
    preset: AquilonPreset,
    instance_ids: list[str],
    target: str = "preview",
    bgcolor: int = 0,
    text_color: int = 16777215,
    text_size: str = "auto",
    smart_wrap: bool = False,
    label: str | None = None,
) -> None:
    """
    Place a single preset button at an exact (row, col) position on a page.

    Raises ValueError if the position is a reserved nav slot.
    """
    if (row, col) in NAV_POSITIONS:
        raise ValueError(f"Cannot place preset at ({row}, {col}) — reserved nav position")

    page_num = str(page_num)
    controls = config["pages"][page_num].setdefault("controls", {})
    btn = build_preset_button(
        preset, instance_ids, target=target,
        bgcolor=bgcolor, text_color=text_color, text_size=text_size,
        smart_wrap=smart_wrap, label=label,
    )
    controls.setdefault(str(row), {})[str(col)] = btn
    logger.debug(f"  [{row}/{col}] pinned memoryId={preset.memory_id} → {label or preset.name!r}")


def apply_presets_to_page(
    config: dict,
    page_num: str | int,
    presets: list[AquilonPreset],
    instance_ids: list[str],
    start_row: int = 0,
    start_col: int = 0,
    cols_per_row: int = 8,
    target: str = "preview",
    bgcolor: int = 0,
    clear_first: bool = True,
    pinned_positions: frozenset[tuple[int, int]] = frozenset(),
    smart_wrap: bool = False,
) -> int:
    """
    Stamp a list of Aquilon presets onto a Companion page as buttons.

    Buttons are placed left-to-right, top-to-bottom starting from
    (start_row, start_col). Nav button positions and any pinned_positions
    are always skipped.

    Args:
        config:           Full Companion config dict (modified in-place).
        page_num:         Target page number (int or string).
        presets:          Ordered list of AquilonPreset objects.
        instance_ids:     Companion instance IDs for each Aquilon unit.
        start_row:        Grid row for the first preset button.
        start_col:        Grid column for the first preset button.
        cols_per_row:     Stream Deck columns per row (XL = 8, regular = 5).
        target:           Action target — "preview" or "program".
        bgcolor:          Background color for all buttons on this page (24-bit int).
        clear_first:      If True, remove existing buttons (preserving nav) first.
        pinned_positions: Additional (row, col) positions to skip during auto-flow
                          (used when buttons have been pinned via place_preset_button).

    Returns:
        Number of presets stamped onto the page.
    """
    page_num = str(page_num)
    controls = config["pages"][page_num].setdefault("controls", {})

    if clear_first:
        # Preserve nav buttons; remove everything else.
        saved_nav: dict[tuple[int, int], dict] = {}
        for row_str, cols in controls.items():
            for col_str, btn in cols.items():
                pos = (int(row_str), int(col_str))
                if pos in NAV_POSITIONS:
                    saved_nav[pos] = btn
        controls.clear()
        for (r, c), btn in saved_nav.items():
            controls.setdefault(str(r), {})[str(c)] = btn
        logger.debug(f"Cleared page {page_num} (preserved {len(saved_nav)} nav buttons)")

    applied = 0
    slot = 0  # counts through nav-safe positions
    for preset in presets:
        # Advance slot until we land on a position that is not a nav button.
        while True:
            flat = (start_row * cols_per_row + start_col) + slot
            row = flat // cols_per_row
            col = flat % cols_per_row
            slot += 1
            if (row, col) not in NAV_POSITIONS and (row, col) not in pinned_positions:
                break

        btn = build_preset_button(preset, instance_ids, target=target, bgcolor=bgcolor, smart_wrap=smart_wrap)
        controls.setdefault(str(row), {})[str(col)] = btn

        logger.debug(f"  [{row}/{col}] memoryId={preset.memory_id} → {preset.name!r}")
        applied += 1

    logger.info(f"Stamped {applied} preset buttons onto page {page_num}")
    return applied


# ---------------------------------------------------------------------------
# Template button builders
# ---------------------------------------------------------------------------

def build_screen_take_button(
    screen_id: int,
    instance_ids: list[str],
    label: str = "TAKE",
    text_color: int = 16777215,
    bgcolor: int = 0,
    text_size: str = "auto",
) -> dict:
    """Build a TAKE button that fires /api/tpp/v1/screens/{screenId}/take on all instances."""
    down_actions = [
        {
            "id": _new_action_id(),
            "type": "action",
            "definitionId": SCREEN_TAKE_ACTION,
            "connectionId": inst_id,
            "options": {"screenId": screen_id},
        }
        for inst_id in instance_ids
    ]
    return {
        "type": "button",
        "style": {
            "text": label,
            "textExpression": False,
            "size": text_size,
            "png64": None,
            "alignment": "center:center",
            "pngalignment": "center:center",
            "color": text_color,
            "bgcolor": bgcolor,
            "show_topbar": "default",
        },
        "options": {"rotaryActions": False, "stepAutoProgress": True},
        "feedbacks": [],
        "steps": {
            "0": {
                "action_sets": {"down": down_actions, "up": []},
                "options": {"runWhileHeld": []},
            }
        },
    }


def build_page_jump_button(
    page: int,
    controller: str = "self",
    label: str = "",
    text_color: int = 16777215,
    bgcolor: int = 0,
    text_size: str = "auto",
) -> dict:
    """
    Build a button that navigates to a specific Companion page.

    Args:
        page:        Target Companion page number.
        controller:  Device serial (e.g. "streamdeck:CL37L2A00862"), "self" for the
                     pressed device, or a Companion variable like "$(custom:green_surface)".
        label:       Button text.
        text_color:  Foreground color as a 24-bit int.
        bgcolor:     Background color as a 24-bit int.
        text_size:   Font size string.
    """
    controller_from_variable = controller.startswith("$(")
    action = {
        "id": _new_action_id(),
        "definitionId": "set_page",
        "connectionId": "internal",
        "options": {
            "controller_from_variable": controller_from_variable,
            "controller": "self" if controller_from_variable else controller,
            "controller_variable": controller if controller_from_variable else "self",
            "page_from_variable": False,
            "page": page,
            "page_variable": "1",
        },
        "type": "action",
        "children": {},
    }
    return {
        "type": "button",
        "style": {
            "text": label,
            "textExpression": False,
            "size": text_size,
            "png64": None,
            "alignment": "center:center",
            "pngalignment": "center:center",
            "color": text_color,
            "bgcolor": bgcolor,
            "show_topbar": "default",
        },
        "options": {"rotaryActions": False, "stepAutoProgress": True},
        "feedbacks": [],
        "steps": {
            "0": {
                "action_sets": {"down": [action], "up": []},
                "options": {"runWhileHeld": []},
            }
        },
    }


def build_label_button(
    label: str,
    text_color: int = 16777215,
    bgcolor: int = 0,
    text_size: str = "auto",
    show_topbar: bool | str = False,
) -> dict:
    """Build a no-action label/reminder button."""
    return {
        "type": "button",
        "style": {
            "text": label,
            "textExpression": False,
            "size": text_size,
            "png64": None,
            "alignment": "center:center",
            "pngalignment": "center:center",
            "color": text_color,
            "bgcolor": bgcolor,
            "show_topbar": show_topbar,
        },
        "options": {"rotaryActions": False, "stepAutoProgress": True},
        "feedbacks": [],
        "steps": {
            "0": {
                "action_sets": {"down": [], "up": []},
                "options": {"runWhileHeld": []},
            }
        },
    }


def place_template_button(
    config: dict,
    page_num: str | int,
    row: int,
    col: int,
    template: dict,
    instance_ids: list[str],
) -> None:
    """
    Place a template button at an exact (row, col) position on a page.

    The template dict comes from [[companion.button_templates]] in config.toml,
    optionally merged with per-placement overrides from the buttons list.

    Supported template actions:
      "screen-take"  — fires /api/tpp/v1/screens/{screenId}/take on all instances
      "label"        — no-action reminder/label button

    Raises ValueError if the position is a reserved nav slot.
    """
    if (row, col) in NAV_POSITIONS:
        raise ValueError(f"Cannot place template at ({row}, {col}) — reserved nav position")

    action = template.get("action")
    label = template.get("label", "")
    bgcolor = template.get("color", 0)
    text_color = template.get("text_color", 16777215)
    text_size = template.get("text_size", "auto")

    if action == "screen-take":
        screen_id = template.get("screen_id", 1)
        btn = build_screen_take_button(screen_id, instance_ids, label, text_color, bgcolor, text_size)
    elif action == "label":
        show_topbar = template.get("show_topbar", False)
        btn = build_label_button(label, text_color, bgcolor, text_size, show_topbar)
    elif action == "page-jump":
        page = template.get("page", 1)
        controller = template.get("controller", "self")
        btn = build_page_jump_button(page, controller, label, text_color, bgcolor, text_size)
    else:
        raise ValueError(f"Unknown template action: {action!r} (supported: 'screen-take', 'label', 'page-jump')")

    page_num = str(page_num)
    controls = config["pages"][page_num].setdefault("controls", {})
    controls.setdefault(str(row), {})[str(col)] = btn
    logger.debug(f"  [{row}/{col}] template {action!r} → {label!r}")


# ---------------------------------------------------------------------------
# Instance helpers
# ---------------------------------------------------------------------------

def get_instance_ids_by_type(config: dict, module_type: str = "analogway-livepremier") -> list[str]:
    """
    Return the Companion instance IDs for all instances of a given module type,
    sorted by their sortOrder field.

    This lets the tool auto-discover AQ21 / AQ22 from the config rather than
    requiring hard-coded IDs.
    """
    instances = config.get("instances", {})
    matches = [
        (inst_id, inst)
        for inst_id, inst in instances.items()
        if inst.get("instance_type") == module_type and inst.get("enabled", True)
    ]
    matches.sort(key=lambda x: x[1].get("sortOrder", 9999))
    ids = [m[0] for m in matches]
    labels = [instances[iid].get("label", iid) for iid in ids]
    logger.debug(f"Found {module_type} instances: {labels}")
    return ids
