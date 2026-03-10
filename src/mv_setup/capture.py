#!/usr/bin/env python3
"""
capture.py — Snapshot all MV memories from the Aquilon into a portable TOML file.

Reads every programmed MV memory from the device and writes a mv_config.toml
with one [[layouts]] block per memory. The resulting file can be applied to
any Aquilon using mv_setup.py.

Usage:
    python src/mv_setup/capture.py --out coachella_mv_config.toml
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonComms
from env import load_env, get_primary_host, get_port

REPO_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_source(s: str) -> tuple[str, int]:
    if s == "NONE":                  return "none", 0
    if s.startswith("IN_"):          return "input", int(s[3:])
    if s.startswith("PROGRAM_S"):    return "screen-program", int(s[9:])
    if s.startswith("PREVIEW_S"):    return "screen-preview", int(s[9:])
    if s.startswith("STILL_"):       return "image", int(s[6:])
    if s.startswith("TIMER_"):       return "timer", int(s[6:])
    return "none", 0


def slug(label: str) -> str:
    return (
        label.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def capture(aq: AquilonComms, out_path: Path) -> None:
    logger.info("Reading MV memory bank from device...")
    device = aq.get_device_state()
    bank_items = device.get("monitoringBank", {}).get("bankList", {}).get("items", {})

    valid = sorted(
        [
            (int(sid), slot)
            for sid, slot in bank_items.items()
            if slot.get("status", {}).get("pp", {}).get("isValid", False)
        ],
        key=lambda x: x[0],
    )

    if not valid:
        logger.error("No programmed MV memories found on the device.")
        sys.exit(1)

    logger.info(f"Found {len(valid)} programmed MV memories.")

    from datetime import date
    today = date.today().isoformat()

    lines = [
        f"# {out_path.name}",
        f"# MV memories captured from {aq.host} on {today}.",
        f"# {len(valid)} layouts total.",
        "#",
        "# Usage:",
        f"#   python src/mv_setup/main.py --config {out_path.name} --list",
        f"#   python src/mv_setup/main.py --config {out_path.name} --layout <name>",
        "",
    ]

    for slot_id, slot in valid:
        label = slot["control"]["pp"]["label"]
        status_pp = slot["status"]["pp"]
        canvas_w = status_pp.get("outputWidth", 1920)
        canvas_h = status_pp.get("outputHeight", 1080)
        widgets_raw = slot["status"]["widgetList"]["items"]

        active = sorted(
            [
                (int(idx), w["pp"])
                for idx, w in widgets_raw.items()
                if w["pp"].get("isEnable", False)
            ],
            key=lambda x: x[0],
        )

        layout_name = f"{slot_id:02d}_{slug(label)}"
        lines += [
            "[[layouts]]",
            f'name     = "{layout_name}"',
            f'# Memory slot {slot_id}: "{label}"',
            f"mv_id    = 1",
            f"canvas_w = {canvas_w}",
            f"canvas_h = {canvas_h}",
            "",
        ]

        for idx, pp in active:
            widget_id = idx + 1  # device is 0-based, REST is 1-based
            src_type, src_id = parse_source(pp["source"])
            lines += ["[[layouts.windows]]", f"widget_id   = {widget_id}", f'source_type = "{src_type}"']
            if src_type != "none":
                lines.append(f"source_id   = {src_id}")
            lines += [
                f'x = {pp["posH"]}',
                f'y = {pp["posV"]}',
                f'w = {pp["sizeH"]}',
                f'h = {pp["sizeV"]}',
                "",
            ]

        logger.info(f"  [{slot_id:2d}] {label!r}  ({len(active)} windows)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote {len(valid)} layouts to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Snapshot all MV memories from the Aquilon into a TOML config file."
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        type=Path,
        required=True,
        help="Output TOML file path (e.g. coachella_mv_config.toml)",
    )
    args = parser.parse_args()

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

    capture(aq, args.out)


if __name__ == "__main__":
    main()
