# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (once)
python -m venv .venv && source .venv/bin/activate
pip install pyyaml python-dotenv
pip install -e ".[dev]"   # adds pytest

cp .env.example .env && cp config.example.toml config.toml
# Fill in AQ_PRIMARY_HOST, AQ_BACKUP_HOST, AQ_PORT in .env
# Fill in memory_ids per page in config.toml

# Tool 1 — Companion Sync
python src/companion_sync/main.py

# Tool 2 — MV Setup
python src/mv_setup/main.py --config mv_config.toml --layout <name>
python src/mv_setup/main.py --config mv_config.toml --list
python src/mv_setup/capture.py --out mv_config.toml        # snapshot device → TOML
python src/mv_setup/restore.py --config mv_config.toml     # restore all MV memories
python src/mv_setup/restore.py --config mv_config.toml --dry-run

# Tests (require live AQ on network)
pytest tests/ -v
pytest tests/test_companion_sync.py::TestPresetButtons -v  # single class
```

## Architecture

Three independent tools sharing `src/common/aquilon_comms.py`. Each tool runs at a different stage of show prep and has its own entry point.

### Tool 1 — Companion Sync (`src/companion_sync/`)
Reads AQ Master Memory names/IDs → stamps them onto Bitfocus Companion YAML config pages.

Flow: `config.toml` page mappings → `aquilon_comms.get_presets()` (REST) → `companion_updater.apply_presets_to_page()` → `outputs/updated.companionconfig`

After writing the output, `main.py` runs a full verification pass and exits non-zero on failure.

Key constraint: nav button positions `(2,7)`, `(3,6)`, `(3,7)` are always skipped. Instance IDs for AQ21+AQ22 are auto-discovered from the template config (no hard-coding).

### Tool 2 — MV Setup (`src/mv_setup/`)
- `main.py` — apply named layouts from TOML to live device
- `capture.py` — snapshot all MV memories from device → portable TOML
- `restore.py` — restore all MV memories from TOML → device (uses `ws_send_batch` for label+save in one session)

Layout TOML format: `[[layouts]]` blocks with `name`, `mv_id`, `canvas_w/h`, and `[[layouts.windows]]` entries (`widget_id`, `source_type`, `source_id`, `x/y/w/h`).

### Tool 3 — AQ Clone (`src/aq_clone/main.py`)
Stub — export/import API endpoints still TBD.

### Common (`src/common/`)
- `aquilon_comms.py` — REST + AWJ WebSocket client. REST for reads and source assignment; WebSocket for geometry, labels, and save triggers. `ws_send_batch([(path, value), ...])` sends multiple AWJ SETs in one persistent session.
- `env.py` — typed accessors for `.env` variables

## Configuration

| File | Purpose |
|------|---------|
| `.env` | `AQ_PRIMARY_HOST`, `AQ_BACKUP_HOST`, `AQ_PORT` (gitignored) |
| `config.toml` | Companion sync page mappings (gitignored) |
| `mv_config.toml` | MV layout definitions (gitignored) |

Both `config.toml` and `mv_config.toml` are gitignored — use `*.example.toml` as templates.

## Key API Details

**LivePremier REST:** `http://<host>/api/tpp/v1/` (dev simulator: `127.0.0.1:3003`)
- Full device state tree: `GET /api/stores/device`
- Memory path: `device.masterPresetBank.bankList.items[id].control.pp.label`

**AWJ WebSocket:** `ws://<host>/api/ws/v1/awj` — used for all SET writes. Dev simulator accepts connections but does NOT process AWJ SET writes.

**Companion config format:** Companion v6 uses YAML (`.companionconfig`). Reference: `example config files for ref/nuc-green_2026_draft.companionconfig`.

## Testing

Tests run against a **live Aquilon only** — no mocking. Requires `.env` with valid AQ IPs and `config.toml` with `memory_ids` populated. `conftest.py` automatically skips tests if `.env` variables are missing.
