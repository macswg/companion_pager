#!/usr/bin/env python3
"""
MV Setup — Analog Way LivePremier multiviewer layout configuration tool.

USE THIS TOOL TO: Apply a named MV window layout from an mv_config.toml file.
  Assigns sources, positions, and sizes for each window.

  Source assignment → REST  POST /api/tpp/v1/multiviewers/{id}/widgets/{id}/source
  Window geometry   → AWJ   WebSocket /api/awj/v1

DO NOT USE THIS TOOL FOR:
  - Companion config files → use src/companion_sync/main.py
  - Output format setup    → use src/aq_setup/main.py
  - Cloning AQ21 to AQ22  → use src/aq_clone/main.py

Usage:
    python src/mv_setup/main.py --config mv_config.toml --layout <name>
    python src/mv_setup/main.py --config mv_config.toml --list
    python src/mv_setup/main.py --list          # uses mv_config.toml by default
"""

import argparse
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
DEFAULT_MV_CONFIG = REPO_ROOT / "mv_config.toml"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "mv_setup.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_mv_config(path: Path) -> dict:
    if not path.exists():
        logger.error(
            f"MV config not found at {path}.\n"
            "Copy mv_config.example.toml and define your layouts."
        )
        sys.exit(1)
    with open(path, "rb") as f:
        return tomllib.load(f)


def apply_layout(aq: AquilonComms, layout: dict) -> None:
    """
    Apply a single layout definition to the device.

    Sets source, position, and size for each configured window.
    Windows not listed in the layout are left unchanged.
    """
    name = layout.get("name", "(unnamed)")
    mv_id = layout.get("mv_id", 1)
    canvas_w = layout.get("canvas_w", 1920)
    canvas_h = layout.get("canvas_h", 1080)
    windows = layout.get("windows", [])

    logger.info(f"Applying layout {name!r} to MV {mv_id} (canvas {canvas_w}×{canvas_h})")

    if not windows:
        logger.warning(f"Layout {name!r} has no windows defined — nothing to do.")
        return

    applied = 0
    errors = 0

    for win in windows:
        widget_id = win.get("widget_id")
        if widget_id is None:
            logger.warning(f"  Window entry missing widget_id — skipping: {win}")
            errors += 1
            continue

        source_type = win.get("source_type", "none")
        source_id = win.get("source_id", 0)
        x = win.get("x", 0)
        y = win.get("y", 0)
        w = win.get("w", 0)
        h = win.get("h", 0)

        if x + w > canvas_w or y + h > canvas_h:
            logger.warning(
                f"  Widget {widget_id}: window ({x},{y}) {w}×{h} exceeds canvas "
                f"{canvas_w}×{canvas_h} — skipping"
            )
            errors += 1
            continue

        label_str = (
            "none" if source_type == "none"
            else f"{source_type}:{source_id}"
        )

        try:
            aq.set_mv_widget_source(mv_id, widget_id, source_type, source_id)
            aq.set_mv_widget_geometry(mv_id, widget_id, x, y, w, h)
            aq.set_mv_widget_enabled(mv_id, widget_id, True)

            logger.info(
                f"  Widget {widget_id:2d}: source={label_str:<24s} "
                f"pos=({x:4d},{y:4d})  size=({w:4d}×{h:4d})"
            )
            applied += 1

        except (ValueError, ConnectionError) as e:
            logger.error(f"  Widget {widget_id}: FAILED — {e}")
            errors += 1

    logger.info(f"Layout {name!r}: applied {applied} windows, {errors} errors.")
    if errors:
        logger.error(f"Layout {name!r} completed with {errors} error(s).")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a multiviewer layout to the primary Aquilon."
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        type=Path,
        default=DEFAULT_MV_CONFIG,
        help=f"Path to MV config TOML file (default: mv_config.toml)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--layout", metavar="NAME", help="Name of the layout to apply.")
    group.add_argument("--list", action="store_true", help="List available layout names.")
    args = parser.parse_args()

    logger.info("===== MV Setup starting =====")
    logger.info(f"Config: {args.config}")

    cfg = load_mv_config(args.config)
    layouts = cfg.get("layouts", [])

    if args.list:
        if not layouts:
            print(f"No layouts defined in {args.config}.")
        else:
            print(f"Layouts in {args.config}:")
            for lay in layouts:
                n = lay.get("name", "(unnamed)")
                mv = lay.get("mv_id", 1)
                wins = len(lay.get("windows", []))
                print(f"  {n!r}  →  MV {mv},  {wins} window(s)")
        sys.exit(0)

    target = next((lay for lay in layouts if lay.get("name") == args.layout), None)
    if target is None:
        available = [lay.get("name", "(unnamed)") for lay in layouts]
        logger.error(
            f"Layout {args.layout!r} not found in {args.config}.\n"
            f"Available: {available}"
        )
        sys.exit(1)

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

    apply_layout(aq, target)

    logger.info("===== MV Setup complete =====")


if __name__ == "__main__":
    main()
