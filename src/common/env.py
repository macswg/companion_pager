"""
env.py — Load environment variables from .env and provide typed accessors.

All tools import from here to get AQ host/port. IPs never appear in config.toml
or source code — they live only in .env (gitignored).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = REPO_ROOT / ".env"


def load_env() -> None:
    """Load .env from the repo root. Call once at startup."""
    if not ENV_FILE.exists():
        print(
            f"ERROR: .env not found at {ENV_FILE}.\n"
            "Copy .env.example → .env and fill in your AQ host IPs.",
            file=sys.stderr,
        )
        sys.exit(1)
    load_dotenv(ENV_FILE)


def get_primary_host() -> str:
    host = os.environ.get("AQ_PRIMARY_HOST", "").strip()
    if not host:
        print("ERROR: AQ_PRIMARY_HOST is not set in .env", file=sys.stderr)
        sys.exit(1)
    return host


def get_backup_host() -> str:
    host = os.environ.get("AQ_BACKUP_HOST", "").strip()
    if not host:
        print("ERROR: AQ_BACKUP_HOST is not set in .env", file=sys.stderr)
        sys.exit(1)
    return host


def get_port() -> int:
    return int(os.environ.get("AQ_PORT", "80"))
