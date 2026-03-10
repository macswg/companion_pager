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

# Nav button positions on a Stream Deck XL (row, col) — must never be overwritten.
# Confirmed from reference config: pageup=row2/col7, pagenum=row3/col6, pagedown=row3/col7.
NAV_POSITIONS: frozenset[tuple[int, int]] = frozenset({
    (2, 7),  # pageup
    (3, 6),  # pagenum
    (3, 7),  # pagedown
})


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
    text_size: str = "18",
    text_color: int = 16777215,   # white
    bgcolor: int = 0,             # black
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
    down_actions = [
        {
            "id": _new_action_id(),
            "action": LOAD_MEMORY_ACTION,
            "instance": inst_id,
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
            "text": preset.name,
            "textExpression": False,
            "size": text_size,
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
) -> int:
    """
    Stamp a list of Aquilon presets onto a Companion page as buttons.

    Buttons are placed left-to-right, top-to-bottom starting from
    (start_row, start_col). Nav button positions are always skipped.

    Args:
        config:       Full Companion config dict (modified in-place).
        page_num:     Target page number (int or string).
        presets:      Ordered list of AquilonPreset objects.
        instance_ids: Companion instance IDs for each Aquilon unit.
        start_row:    Grid row for the first preset button.
        start_col:    Grid column for the first preset button.
        cols_per_row: Stream Deck columns per row (XL = 8, regular = 5).
        target:       Action target — "preview" or "program".
        bgcolor:      Background color for all buttons on this page (24-bit int).
        clear_first:  If True, remove existing buttons (preserving nav) first.

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
            if (row, col) not in NAV_POSITIONS:
                break

        btn = build_preset_button(preset, instance_ids, target=target, bgcolor=bgcolor)
        controls.setdefault(str(row), {})[str(col)] = btn

        logger.debug(f"  [{row}/{col}] memoryId={preset.memory_id} → {preset.name!r}")
        applied += 1

    logger.info(f"Stamped {applied} preset buttons onto page {page_num}")
    return applied


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
