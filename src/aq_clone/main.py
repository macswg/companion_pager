#!/usr/bin/env python3
"""
AQ Clone — Aquilon config clone tool.

USE THIS TOOL TO: Copy the full show config from AQ21 (primary) to AQ22 (backup)
and verify both units have identical memory lists.

Steps performed:
  1. Export config from AQ21
  2. Import that config to AQ22
  3. Query memory lists from both units
  4. Assert they are identical — same IDs, names, and count
  5. Report pass/fail. Exit non-zero on any failure.

DO NOT USE THIS TOOL FOR:
  - Companion config files → use src/companion_sync/main.py
  - Output mode config     → use src/aq_setup/main.py
  - Multiviewer layouts    → use src/mv_setup/main.py

Usage:
    python src/aq_clone/main.py

TODO: Implement export/import once the LivePremier API mechanism is confirmed.
      Likely a GET to download a config blob from AQ21 followed by a POST/PUT
      to upload it to AQ22. Exact endpoints unknown — check /api/tpp/v1/ docs.
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
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "aq_clone.log"),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_FILE = REPO_ROOT / "config.toml"


def load_app_config() -> dict:
    if not CONFIG_FILE.exists():
        logger.error(
            f"config.toml not found at {CONFIG_FILE}.\n"
            "Copy config.example.toml → config.toml and fill in your settings."
        )
        sys.exit(1)
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


def verify_units_match(primary: AquilonComms, backup: AquilonComms) -> bool:
    """
    Query memory lists from both units and assert they are identical.

    Returns True if they match, False if any discrepancy is found.
    Logs a detailed diff if they do not match.
    """
    logger.info("Verifying AQ21 and AQ22 memory lists match...")

    primary_presets = primary.get_presets()
    backup_presets = backup.get_presets()

    primary_map = {p.memory_id: p.name for p in primary_presets}
    backup_map = {p.memory_id: p.name for p in backup_presets}

    passed = True

    # Check counts
    if len(primary_presets) != len(backup_presets):
        logger.error(
            f"FAIL: Memory count mismatch — "
            f"AQ21 has {len(primary_presets)}, AQ22 has {len(backup_presets)}"
        )
        passed = False

    # Check every primary memory exists on backup with the same name
    for mem_id, name in primary_map.items():
        if mem_id not in backup_map:
            logger.error(f"FAIL: Memory {mem_id} ({name!r}) present on AQ21 but missing from AQ22")
            passed = False
        elif backup_map[mem_id] != name:
            logger.error(
                f"FAIL: Memory {mem_id} name mismatch — "
                f"AQ21: {name!r}, AQ22: {backup_map[mem_id]!r}"
            )
            passed = False

    # Check for anything on backup that isn't on primary
    for mem_id, name in backup_map.items():
        if mem_id not in primary_map:
            logger.error(f"FAIL: Memory {mem_id} ({name!r}) present on AQ22 but missing from AQ21")
            passed = False

    if passed:
        logger.info(f"PASS: Both units have identical memory lists ({len(primary_presets)} memories)")

    return passed


def main() -> None:
    logger.info("===== AQ Clone starting =====")

    load_env()
    primary_host = get_primary_host()
    backup_host = get_backup_host()
    port = get_port()

    primary = AquilonComms(host=primary_host, port=port)
    backup = AquilonComms(host=backup_host, port=port)

    # Step 1: Export config from primary
    # TODO: implement export once API endpoint is confirmed
    logger.warning("TODO: Export from AQ21 not yet implemented — API endpoint unknown.")

    # Step 2: Import config to backup
    # TODO: implement import once API endpoint is confirmed
    logger.warning("TODO: Import to AQ22 not yet implemented — API endpoint unknown.")

    # Step 3: Verify both units match
    matched = verify_units_match(primary, backup)

    if not matched:
        logger.error("AQ Clone FAILED — units do not match. Do not proceed to show.")
        sys.exit(1)

    logger.info("===== AQ Clone complete =====")


if __name__ == "__main__":
    main()
