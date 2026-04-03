#!/usr/bin/env python3
"""
verify.py — check that a Companion config is up to date with live Aquilon presets.

For every memory_id listed in config.toml, confirms that:
  - A button exists on the expected page with that memoryId in its action
  - The button label matches the current preset name on the device

Usage:
    companion-verify                          # checks most recent file in outputs/
    companion-verify path/to/file.companionconfig
    companion-verify --config other.toml path/to/file.companionconfig
"""

import argparse
import logging
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "common"))

from aquilon_comms import AquilonComms
from .companion_updater import get_instance_ids_by_type, load_config
from env import get_port, get_primary_host, load_env

REPO_ROOT = Path(__file__).parent.parent.parent
LOAD_MEMORY_ACTION = "/api/tpp/v1/load-master-memory"

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a Companion config is up to date with live Aquilon presets"
    )
    parser.add_argument(
        "companionconfig",
        nargs="?",
        type=Path,
        help="Path to the .companionconfig file to check. "
             "Defaults to the most recent file in outputs/.",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=REPO_ROOT / "config.toml",
        help="Path to config.toml (default: config.toml)",
    )
    return parser.parse_args()


def pick_file_dialog() -> Path | None:
    """Open a native file picker and return the selected path, or None if cancelled."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()  # hide the empty root window
        root.attributes("-topmost", True)
        chosen = filedialog.askopenfilename(
            title="Select Companion config to verify",
            initialdir=str(REPO_ROOT / "outputs"),
            filetypes=[("Companion config", "*.companionconfig"), ("All files", "*.*")],
        )
        root.destroy()
        return Path(chosen) if chosen else None
    except Exception:
        return None


def find_latest_output() -> Path:
    outputs_dir = REPO_ROOT / "outputs"
    files = sorted(outputs_dir.glob("*.companionconfig"), key=lambda p: p.stat().st_mtime)
    if not files:
        print("ERROR: No .companionconfig files found in outputs/")
        sys.exit(1)
    return files[-1]


def get_load_memory_actions(btn: dict) -> list[dict]:
    try:
        actions = btn["steps"]["0"]["action_sets"]["down"]
        return [a for a in actions if a.get("definitionId") == LOAD_MEMORY_ACTION]
    except (KeyError, TypeError):
        return []


def collect_buttons_by_memory_id(controls: dict) -> dict[int, list[dict]]:
    """Return {memoryId: [button, ...]} for all preset buttons on a page."""
    result: dict[int, list[dict]] = {}
    for row in controls.values():
        for btn in row.values():
            for action in get_load_memory_actions(btn):
                mid = action["options"]["memoryId"]
                result.setdefault(mid, []).append(btn)
    return result


def verify_pages(
    pages_cfg: list[dict],
    companion_cfg: dict,
    preset_map: dict[int, str],
) -> tuple[list[str], int]:
    """
    Core verification logic — callable from both companion-verify and companion-sync --verify.

    Returns (failures, total_checked) where failures is a flat list of human-readable
    error strings (empty if everything passed).
    """
    failures: list[str] = []
    checked = 0

    for page_cfg in pages_cfg:
        page_num = str(page_cfg["page_num"])
        memory_ids = page_cfg.get("memory_ids", [])
        if not memory_ids:
            continue

        controls = (
            companion_cfg.get("pages", {})
            .get(page_num, {})
            .get("controls", {})
        )
        buttons_by_mid = collect_buttons_by_memory_id(controls)
        page_failures: list[str] = []

        for mid in memory_ids:
            checked += 1
            expected_name = preset_map.get(mid)

            if expected_name is None:
                page_failures.append(f"  memoryId {mid}: not found on device (skipping label check)")
                continue

            btns = buttons_by_mid.get(mid)
            if not btns:
                page_failures.append(f"  memoryId {mid} ({expected_name!r}): MISSING — no button on page")
                continue

            actual_label = btns[0].get("style", {}).get("text", "")
            if actual_label != expected_name:
                page_failures.append(
                    f"  memoryId {mid}: label mismatch\n"
                    f"    config has: {actual_label!r}\n"
                    f"    device has: {expected_name!r}"
                )

        if page_failures:
            failures.append(f"Page {page_num} ({page_cfg.get('page_title', '')}):")
            failures.extend(page_failures)
        else:
            print(f"  Page {page_num}: OK ({len(memory_ids)} presets)")

    return failures, checked


def main() -> None:
    args = parse_args()

    load_env()

    # --- Load config.toml ---
    config_path = args.config
    if not config_path.exists():
        print(f"ERROR: config not found at {config_path}")
        sys.exit(1)
    with open(config_path, "rb") as f:
        app_config = tomllib.load(f)

    # --- Resolve which companionconfig to check ---
    if args.companionconfig:
        check_path = args.companionconfig
    else:
        check_path = pick_file_dialog()
        if check_path is None:
            print("No file selected — using most recent output.")
            check_path = find_latest_output()
    if not check_path.exists():
        print(f"ERROR: file not found: {check_path}")
        sys.exit(1)

    print(f"Checking: {check_path.relative_to(REPO_ROOT)}")

    # --- Load the companionconfig ---
    companion_cfg = load_config(check_path)

    # --- Auto-discover instance IDs ---
    instance_ids = get_instance_ids_by_type(companion_cfg, "analogway-livepremier")
    if not instance_ids:
        print("ERROR: No analogway-livepremier instances found in the config file.")
        sys.exit(1)

    # --- Fetch live presets from the Aquilon ---
    aq_host = get_primary_host()
    aq_port = get_port()
    print(f"Querying Aquilon at {aq_host}:{aq_port} ...")
    try:
        presets = AquilonComms(host=aq_host, port=aq_port).get_presets()
    except ConnectionError as e:
        print(f"ERROR: Could not reach Aquilon: {e}")
        sys.exit(1)

    preset_map: dict[int, str] = {p.memory_id: p.name for p in presets}
    print(f"Retrieved {len(preset_map)} presets from device.\n")

    # --- Run verification ---
    pages_cfg = app_config["companion"].get("pages", [])
    failures, checked = verify_pages(pages_cfg, companion_cfg, preset_map)

    print()
    if failures:
        print(f"FAIL — {len(failures)} issue(s) found across {checked} checked presets:\n")
        for line in failures:
            print(line)
        sys.exit(1)
    else:
        print(f"PASS — all {checked} preset buttons match live Aquilon presets.")


if __name__ == "__main__":
    main()
