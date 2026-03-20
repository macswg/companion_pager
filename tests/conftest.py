"""
conftest.py — shared pytest fixtures.

Host IPs come from .env (same file used by the tools).
Structural config (template path, page settings) comes from config.toml.
"""

import sys
import tomllib
from pathlib import Path

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent
ENV_FILE = REPO_ROOT / ".env"
CONFIG_FILE = REPO_ROOT / "config.toml"

# Load .env at import time so all fixtures can read os.environ
if not ENV_FILE.exists():
    pytest.skip(
        f".env not found at {ENV_FILE} — copy .env.example and set your AQ host IPs.",
        allow_module_level=True,
    )
load_dotenv(ENV_FILE)

import os  # noqa: E402 — must come after load_dotenv


def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        pytest.skip(f"{key} is not set in .env")
    return val


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_config() -> dict:
    if not CONFIG_FILE.exists():
        pytest.skip("config.toml not found — copy config.example.toml first.")
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)


@pytest.fixture(scope="session")
def primary_host() -> str:
    return _require_env("AQ_PRIMARY_HOST")


@pytest.fixture(scope="session")
def backup_host() -> str:
    return _require_env("AQ_BACKUP_HOST")


@pytest.fixture(scope="session")
def aq_port() -> int:
    return int(os.environ.get("AQ_PORT", "80"))


# ---------------------------------------------------------------------------
# Live AQ fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def live_presets(primary_host, aq_port):
    """Preset list from the live primary Aquilon. Cached for the test session."""
    sys.path.insert(0, str(REPO_ROOT / "src" / "common"))
    from aquilon_comms import AquilonComms

    aq = AquilonComms(host=primary_host, port=aq_port)
    try:
        return aq.get_presets()
    except ConnectionError as e:
        pytest.skip(f"Primary AQ not reachable at {primary_host}:{aq_port}: {e}")


@pytest.fixture(scope="session")
def instance_ids(app_config) -> list[str]:
    """Companion instance IDs for all LivePremier units, from the template config."""
    import yaml
    sys.path.insert(0, str(REPO_ROOT / "src" / "companion_sync"))
    from companion_updater import get_instance_ids_by_type

    template_path = REPO_ROOT / app_config["companion"]["template_path"]
    with open(template_path, "r") as f:
        config = yaml.safe_load(f)
    return get_instance_ids_by_type(config, "analogway-livepremier")
