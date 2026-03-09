#!/usr/bin/env python3
"""
MV Setup — Analog Way LivePremier multiviewer layout configuration tool.

USE THIS TOOL TO: Configure multiviewer window layouts on Aquilon outputs.
  - Position and size MV windows
  - Assign sources to MV windows
  - Set window titling (source name, output number, etc.)
  - Support multiple MV output configurations

DO NOT USE THIS TOOL FOR:
  - Companion config files → use src/companion_sync/main.py
  - Aquilon device setup   → use src/aq_setup/main.py

Usage:
    python src/mv_setup/main.py

TODO: Implement MV layout routines.
"""

import logging
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonComms
from env import load_env, get_primary_host, get_port

REPO_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "mv_setup.log"),
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


def main() -> None:
    logger.info("===== MV Setup starting =====")

    load_env()
    cfg = load_app_config()
    aq_host = get_primary_host()
    aq_port = get_port()

    aquilon = AquilonComms(host=aq_host, port=aq_port)

    # TODO: implement MV layout routines
    logger.info(f"Connected to AQ at {aq_host}:{aq_port}")
    logger.warning("MV Setup is not yet implemented.")

    logger.info("===== MV Setup complete =====")


if __name__ == "__main__":
    main()
