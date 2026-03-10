#!/usr/bin/env python3
"""
restore.py — Restore all MV memories from a TOML config file to an Aquilon.

Reads every [[layouts]] block from an mv_config.toml, applies each layout to
the live MV output, sets the memory slot label, then triggers a save.  After
running, the device's MV memory bank will match the captured config.

Slot IDs are read from the layout name prefix (e.g. "01_inputs" → slot 1).
The name must begin with one or more digits followed by an underscore.

Usage:
    python src/mv_setup/restore.py --config coachella_mv_config.toml
    python src/mv_setup/restore.py --config coachella_mv_config.toml --dry-run
"""

import argparse
import logging
import re
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonComms
from env import load_env, get_primary_host, get_port

# Import apply_layout from the sibling main module without creating a package
import importlib.util as _ilu
_main_spec = _ilu.spec_from_file_location("mv_setup_main", Path(__file__).parent / "main.py")
_main_mod = _ilu.module_from_spec(_main_spec)
_main_spec.loader.exec_module(_main_mod)
apply_layout = _main_mod.apply_layout

REPO_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "mv_restore.log"),
    ],
)
logger = logging.getLogger(__name__)

_SLOT_RE = re.compile(r"^(\d+)_")

SAVE_DELAY_S = 0.5  # seconds to wait between save triggers


def parse_slot_id(name: str) -> int | None:
    """Return the slot number from a layout name like '01_inputs', or None."""
    m = _SLOT_RE.match(name)
    return int(m.group(1)) if m else None


def restore(aq: AquilonComms, layouts: list[dict], dry_run: bool) -> None:
    ok = 0
    skipped = 0
    errors = 0

    for layout in layouts:
        name = layout.get("name", "(unnamed)")
        slot_id = parse_slot_id(name)

        if slot_id is None:
            logger.warning(
                f"Cannot determine slot ID from layout name {name!r} "
                "(must start with digits and underscore, e.g. '01_inputs') — skipping"
            )
            skipped += 1
            continue

        # Reconstruct the human-readable label: strip leading "NN_" and replace _ with space
        label = re.sub(r"^\d+_", "", name).replace("_", " ")

        logger.info(f"[slot {slot_id:2d}] {name!r}  →  label={label!r}")

        if dry_run:
            wins = len(layout.get("windows", []))
            logger.info(f"  DRY-RUN: would apply {wins} window(s), set label, save")
            ok += 1
            continue

        try:
            # 1. Apply the layout to the live MV output
            apply_layout(aq, layout)

            # 2. Set label and trigger save in one WebSocket session
            aq.save_mv_memory(slot_id, label=label)

            ok += 1
            time.sleep(SAVE_DELAY_S)

        except SystemExit:
            logger.error(f"  [slot {slot_id}] apply_layout reported errors — slot not saved")
            errors += 1
        except (ValueError, ConnectionError) as e:
            logger.error(f"  FAILED: {e}")
            errors += 1

    logger.info(
        f"Restore complete: {ok} saved, {skipped} skipped, {errors} errors."
    )
    if errors:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore all MV memories from a TOML config file to an Aquilon."
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        type=Path,
        required=True,
        help="Path to mv_config TOML file (e.g. coachella_mv_config.toml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse the config and log what would happen without touching the device.",
    )
    args = parser.parse_args()

    if not args.config.exists():
        logger.error(f"Config file not found: {args.config}")
        sys.exit(1)

    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)

    layouts = cfg.get("layouts", [])
    if not layouts:
        logger.error(f"No [[layouts]] found in {args.config}")
        sys.exit(1)

    logger.info(f"===== MV Restore starting =====")
    logger.info(f"Config: {args.config}  ({len(layouts)} layouts)")
    if args.dry_run:
        logger.info("DRY-RUN mode — device will not be modified")

    if not args.dry_run:
        load_env()
        aq_host = get_primary_host()
        aq_port = get_port()
        logger.info(f"Connecting to primary AQ at {aq_host}:{aq_port}")
        aq = AquilonComms(host=aq_host, port=aq_port)

        try:
            info = aq.get_system_info()
            logger.info(
                f"Connected: {info.get('type')} — {info.get('label')} — "
                f"firmware {info.get('version', {}).get('major')}."
                f"{info.get('version', {}).get('minor')}."
                f"{info.get('version', {}).get('patch')}"
            )
        except ConnectionError as e:
            logger.error(f"Cannot reach AQ at {aq_host}:{aq_port}: {e}")
            sys.exit(1)
    else:
        aq = None  # not used in dry-run

    restore(aq, layouts, dry_run=args.dry_run)
    logger.info("===== MV Restore complete =====")


if __name__ == "__main__":
    main()
