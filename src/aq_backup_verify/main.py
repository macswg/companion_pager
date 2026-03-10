#!/usr/bin/env python3
"""
AQ Backup Checker — verify AQ22 matches AQ21.

USE THIS TOOL TO: Confirm that AQ22 (backup) is in sync with AQ21 (primary).
Checks firmware version and Master Memory lists on both units and reports
any discrepancies.

Usage:
    python src/aq_backup_verify/main.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonComms
from env import load_env, get_primary_host, get_backup_host, get_port

REPO_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "aq_backup_checker.log"),
    ],
)
logger = logging.getLogger(__name__)


def verify_system_info(primary: AquilonComms, backup: AquilonComms) -> bool:
    """
    Compare system info (firmware, device type) between both units.
    Returns True if they match, False if any discrepancy is found.
    """
    logger.info("Checking system info...")

    primary_info = primary.get_system_info()
    backup_info = backup.get_system_info()

    logger.info(f"  AQ21: {primary_info}")
    logger.info(f"  AQ22: {backup_info}")

    passed = True
    for key in ("firmware", "deviceType"):
        pval = primary_info.get(key)
        bval = backup_info.get(key)
        if pval != bval:
            logger.error(f"FAIL: {key} mismatch — AQ21: {pval!r}, AQ22: {bval!r}")
            passed = False

    if passed:
        logger.info(f"PASS: System info matches (firmware: {primary_info.get('firmware')!r})")

    return passed


def verify_presets(primary: AquilonComms, backup: AquilonComms) -> bool:
    """
    Compare Master Memory lists between both units.
    Returns True if they match, False if any discrepancy is found.
    """
    logger.info("Checking Master Memory lists...")

    primary_presets = primary.get_presets()
    backup_presets = backup.get_presets()

    primary_map = {p.memory_id: p.name for p in primary_presets}
    backup_map = {p.memory_id: p.name for p in backup_presets}

    passed = True

    if len(primary_presets) != len(backup_presets):
        logger.error(
            f"FAIL: Memory count mismatch — "
            f"AQ21 has {len(primary_presets)}, AQ22 has {len(backup_presets)}"
        )
        passed = False

    for mem_id, name in primary_map.items():
        if mem_id not in backup_map:
            logger.error(f"FAIL: Memory {mem_id} ({name!r}) on AQ21 but missing from AQ22")
            passed = False
        elif backup_map[mem_id] != name:
            logger.error(
                f"FAIL: Memory {mem_id} name mismatch — "
                f"AQ21: {name!r}, AQ22: {backup_map[mem_id]!r}"
            )
            passed = False

    for mem_id, name in backup_map.items():
        if mem_id not in primary_map:
            logger.error(f"FAIL: Memory {mem_id} ({name!r}) on AQ22 but missing from AQ21")
            passed = False

    if passed:
        logger.info(f"PASS: Memory lists match ({len(primary_presets)} memories)")

    return passed


def verify_inputs(primary: AquilonComms, backup: AquilonComms) -> bool:
    """Compare input labels between both units."""
    logger.info("Checking inputs...")

    primary_inputs = {i["id"]: i for i in primary.get_inputs()}
    backup_inputs = {i["id"]: i for i in backup.get_inputs()}

    passed = True

    if set(primary_inputs) != set(backup_inputs):
        logger.error(
            f"FAIL: Input ID sets differ — "
            f"AQ21: {sorted(primary_inputs)}, AQ22: {sorted(backup_inputs)}"
        )
        passed = False

    for input_id, pi in primary_inputs.items():
        bi = backup_inputs.get(input_id)
        if bi is None:
            continue  # already reported above
        if pi.get("label") != bi.get("label"):
            logger.error(
                f"FAIL: Input {input_id} label mismatch — "
                f"AQ21: {pi.get('label')!r}, AQ22: {bi.get('label')!r}"
            )
            passed = False

    if passed:
        logger.info(f"PASS: Inputs match ({len(primary_inputs)} inputs)")

    return passed


def verify_screens(primary: AquilonComms, backup: AquilonComms) -> bool:
    """Compare screen labels and enabled state between both units."""
    logger.info("Checking screens...")

    primary_screens = {s["id"]: s for s in primary.get_screens()}
    backup_screens = {s["id"]: s for s in backup.get_screens()}

    passed = True

    if set(primary_screens) != set(backup_screens):
        logger.error(
            f"FAIL: Screen ID sets differ — "
            f"AQ21: {sorted(primary_screens)}, AQ22: {sorted(backup_screens)}"
        )
        passed = False

    for screen_id, ps in primary_screens.items():
        bs = backup_screens.get(screen_id)
        if bs is None:
            continue
        for key in ("label", "isEnabled"):
            if ps.get(key) != bs.get(key):
                logger.error(
                    f"FAIL: Screen {screen_id} {key!r} mismatch — "
                    f"AQ21: {ps.get(key)!r}, AQ22: {bs.get(key)!r}"
                )
                passed = False

    if passed:
        logger.info(f"PASS: Screens match ({len(primary_screens)} screens)")

    return passed


def verify_outputs(primary: AquilonComms, backup: AquilonComms) -> bool:
    """Compare output labels and formats between both units."""
    logger.info("Checking outputs...")

    primary_outputs = {o.output_id: o for o in primary.get_outputs()}
    backup_outputs = {o.output_id: o for o in backup.get_outputs()}

    passed = True

    if set(primary_outputs) != set(backup_outputs):
        logger.error(
            f"FAIL: Output ID sets differ — "
            f"AQ21: {sorted(primary_outputs)}, AQ22: {sorted(backup_outputs)}"
        )
        passed = False

    for out_id, po in primary_outputs.items():
        bo = backup_outputs.get(out_id)
        if bo is None:
            continue
        if po.label != bo.label:
            logger.error(
                f"FAIL: Output {out_id} label mismatch — "
                f"AQ21: {po.label!r}, AQ22: {bo.label!r}"
            )
            passed = False
        if po.current_format != bo.current_format:
            logger.error(
                f"FAIL: Output {out_id} format mismatch — "
                f"AQ21: {po.current_format!r}, AQ22: {bo.current_format!r}"
            )
            passed = False

    if passed:
        logger.info(f"PASS: Outputs match ({len(primary_outputs)} outputs)")

    return passed


def main() -> None:
    logger.info("===== AQ Backup Checker starting =====")

    load_env()
    primary_host = get_primary_host()
    backup_host = get_backup_host()
    port = get_port()

    logger.info(f"Primary (AQ21): {primary_host}:{port}")
    logger.info(f"Backup  (AQ22): {backup_host}:{port}")

    primary = AquilonComms(host=primary_host, port=port)
    backup = AquilonComms(host=backup_host, port=port)

    results = [
        verify_system_info(primary, backup),
        verify_inputs(primary, backup),
        verify_screens(primary, backup),
        verify_outputs(primary, backup),
        verify_presets(primary, backup),
    ]

    if all(results):
        logger.info("===== PASS: AQ21 and AQ22 are in sync =====")
    else:
        logger.error("===== FAIL: Units are out of sync — do not proceed to show =====")
        sys.exit(1)


if __name__ == "__main__":
    main()
