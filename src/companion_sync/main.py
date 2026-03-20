#!/usr/bin/env python3
"""
main.py — companion-pager entry point.

Workflow:
  1. Load config.toml (copy config.example.toml to start).
  2. Load the Companion config template (YAML).
  3. Auto-discover Analog Way LivePremier instance IDs from the template.
  4. Query the LivePremier for all Master Memory names and IDs.
  5. Stamp preset buttons onto the designated page(s).
  6. Write the updated config to the output path (import into Companion).

Usage:
    python src/companion_sync/main.py
"""

import argparse
import logging
import sys
import tomllib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonComms
from env import load_env, get_primary_host, get_port
from companion_updater import (
    apply_presets_to_page,
    get_instance_ids_by_type,
    load_config,
    place_preset_button,
    place_template_button,
    save_config,
    update_page_title,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "companion_pager.log"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_FILE = REPO_ROOT / "config.toml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="companion-pager: stamp AQ presets onto Companion pages")
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=DEFAULT_CONFIG_FILE,
        help="Path to config TOML (default: config.toml)",
    )
    return parser.parse_args()


def load_app_config(config_path: Path) -> dict:
    if not config_path.exists():
        logger.error(
            f"Config not found at {config_path}.\n"
            "Copy config.example.toml → config.toml and fill in your settings."
        )
        sys.exit(1)
    with open(config_path, "rb") as f:
        return tomllib.load(f)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    logger.info("===== companion-pager starting =====")

    load_env()
    cfg = load_app_config(args.config)

    # Aquilon (LivePremier) connection — host/port from .env
    aq_host = get_primary_host()
    aq_port = get_port()

    # Companion config paths
    template_path = REPO_ROOT / cfg["companion"]["template_path"]
    raw_output = REPO_ROOT / cfg["companion"]["output_path"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = raw_output.parent / f"{raw_output.stem}_{timestamp}{raw_output.suffix}"

    cols_per_row = cfg["companion"].get("cols_per_row", 8)
    target = cfg["companion"].get("target", "preview")
    smart_wrap = cfg["companion"].get("smart_wrap", False)
    pages_config = cfg["companion"].get("pages", [])
    templates = {t["name"]: t for t in cfg["companion"].get("button_templates", [])}

    # --- Step 1: Load template config ---
    logger.info(f"Loading template: {template_path}")
    config = load_config(template_path)

    # --- Step 2: Auto-discover Aquilon instances ---
    instance_ids = get_instance_ids_by_type(config, "analogway-livepremier")
    if not instance_ids:
        logger.error(
            "No analogway-livepremier instances found in the template config.\n"
            "Make sure the template has at least one enabled LivePremier instance."
        )
        sys.exit(1)
    logger.info(f"Found {len(instance_ids)} LivePremier instance(s): {instance_ids}")

    # --- Step 3: Query presets from the LivePremier ---
    logger.info(f"Connecting to Aquilon (LivePremier) at {aq_host}:{aq_port}")
    aquilon = AquilonComms(host=aq_host, port=aq_port)
    try:
        presets = aquilon.get_presets()
    except ConnectionError as e:
        logger.error(f"Failed to retrieve presets from LivePremier: {e}")
        sys.exit(1)

    if not presets:
        logger.warning("No presets returned from the LivePremier — nothing to do.")
        sys.exit(0)

    logger.info(f"Retrieved {len(presets)} presets:")
    for p in presets:
        logger.info(f"  [{p.memory_id:3d}] {p.name}")

    # --- Step 4: Update each configured page ---
    preset_map = {p.memory_id: p for p in presets}
    total_stamped = 0

    if not pages_config:
        logger.warning(
            "No [[companion.pages]] entries in config.toml — nothing to stamp.\n"
            "Add at least one [[companion.pages]] block with page_num and memory_ids."
        )
    else:
        for page_cfg in pages_config:
            page_num = page_cfg["page_num"]
            page_title = page_cfg.get("page_title", f"Page {page_num}")
            bgcolor = page_cfg.get("color", 0)
            memory_ids = page_cfg.get("memory_ids", [])

            page_presets = [preset_map[mid] for mid in memory_ids if mid in preset_map]
            missing = [mid for mid in memory_ids if mid not in preset_map]
            if missing:
                logger.warning(
                    f"Page {page_num}: {len(missing)} memory ID(s) not found on device: {missing}"
                )

            update_page_title(config, page_num, page_title)

            # Step 1: clear the page (preserving nav), unless clear=false in config.
            clear_first = page_cfg.get("clear", True)
            apply_presets_to_page(
                config, page_num=page_num, presets=[],
                instance_ids=instance_ids, clear_first=clear_first,
            )

            # Step 2: place pinned buttons at exact positions.
            pinned_cfg = page_cfg.get("buttons", [])
            pinned_positions = set()
            for pin in pinned_cfg:
                row, col = pin["row"], pin["col"]
                try:
                    if "template" in pin:
                        tname = pin["template"]
                        if tname not in templates:
                            logger.warning(f"Page {page_num}: unknown template {tname!r}, skipping.")
                            continue
                        # merge template defaults with any per-placement overrides
                        merged = {**templates[tname], **{k: v for k, v in pin.items() if k not in ("template", "row", "col")}}
                        if merged.get("action") == "preset":
                            mid = merged.get("memory_id")
                            if mid is None:
                                logger.warning(f"Page {page_num}: template {tname!r} has action='preset' but no memory_id, skipping.")
                                continue
                            if mid not in preset_map:
                                logger.warning(f"Page {page_num}: template {tname!r} memory_id {mid} not found on device, skipping.")
                                continue
                            # Use explicit label if set, else fall back to device name.
                            label = merged.get("label") or None
                            place_preset_button(
                                config, page_num, row, col,
                                preset=preset_map[mid],
                                instance_ids=instance_ids,
                                target=target,
                                bgcolor=merged.get("color", bgcolor),
                                text_color=merged.get("text_color", 16777215),
                                text_size=merged.get("text_size", "auto"),
                                smart_wrap=smart_wrap,
                                label=label,
                            )
                        else:
                            place_template_button(config, page_num, row, col, merged, instance_ids)
                    elif "action" in pin:
                        place_template_button(config, page_num, row, col, pin, instance_ids)
                    else:
                        mid = pin["memory_id"]
                        if mid not in preset_map:
                            logger.warning(f"Page {page_num}: pinned memory_id {mid} not found on device, skipping.")
                            continue
                        place_preset_button(
                            config, page_num, row, col,
                            preset=preset_map[mid],
                            instance_ids=instance_ids,
                            target=target,
                            bgcolor=pin.get("color", bgcolor),
                            text_color=pin.get("text_color", 16777215),
                            text_size=pin.get("text_size", "auto"),
                            smart_wrap=smart_wrap,
                        )
                    pinned_positions.add((row, col))
                    total_stamped += 1
                except ValueError as e:
                    logger.error(f"Page {page_num}: {e}")

            # Step 3: auto-flow remaining presets into open slots.
            if not page_presets:
                if not pinned_cfg:
                    logger.warning(f"Page {page_num}: no matching presets found, skipping.")
                continue

            n = apply_presets_to_page(
                config,
                page_num=page_num,
                presets=page_presets,
                instance_ids=instance_ids,
                cols_per_row=cols_per_row,
                target=target,
                bgcolor=bgcolor,
                clear_first=False,
                pinned_positions=frozenset(pinned_positions),
                smart_wrap=smart_wrap,
            )
            logger.info(f"Page {page_num} ({page_title!r}): {n} auto-flow + {len(pinned_positions)} pinned.")
            total_stamped += n

    logger.info(f"Total preset buttons stamped: {total_stamped}")

    # --- Step 5: Save output ---
    save_config(config, output_path)
    logger.info(f"Done. Import {output_path} into Companion.")
    logger.info("===== companion-pager complete =====")


if __name__ == "__main__":
    main()
