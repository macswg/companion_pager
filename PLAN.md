# Implementation Plan — Aquilon Show Control Toolkit

## Tools in this Repo

Each tool is independent. They share a common REST client but are run at
different stages of show prep.

| Tool | Entry Point | Purpose | Stage |
|------|-------------|---------|-------|
| **Companion Sync** | `src/companion_sync/main.py` | AQ preset names → Companion buttons | After presets named |
| **MV Setup** | `src/mv_setup/main.py` | Configure multiviewer window layouts | Show build |
| **AQ Backup Verify** | `src/aq_backup_verify/main.py` | Verify AQ22 firmware + memories match AQ21 | On demand |

All tools share `src/common/aquilon_comms.py` as the LivePremier REST + WebSocket API client.

---

## Repo Structure

```
companion_pager/
├── config.example.toml              ← copy → config.toml (gitignored)
├── mv_config.example.toml           ← copy → mv_config.toml (gitignored)
├── PRD.md / PLAN.md / README.md
├── pyproject.toml                   ← dependencies: pyyaml, python-dotenv
├── example config files for ref/
│   └── nuc-green_2026_draft.companionconfig  ← 2025 show reference layout
├── src/
│   ├── companion_sync/              ← TOOL 1: Companion preset sync
│   │   ├── main.py
│   │   └── companion_updater.py
│   ├── mv_setup/                    ← TOOL 2: Multiviewer layout configuration
│   │   ├── main.py                  ← apply named layout from TOML to device
│   │   ├── capture.py               ← snapshot device MV memories → TOML
│   │   └── restore.py               ← restore all MV memories from TOML → device
│   ├── aq_backup_verify/            ← TOOL 3: Verify AQ22 matches AQ21
│   │   └── main.py
│   └── common/                      ← shared (not a tool)
│       ├── aquilon_comms.py
│       └── env.py
├── outputs/                         ← gitignored; generated configs land here
└── logs/                            ← gitignored; log files land here
```

---

## Reference: 2025 Show Config

Key facts from `nuc-green_2026_draft.companionconfig`:

| Detail | Value |
|--------|-------|
| Companion version | 6 |
| Config format | YAML |
| AQ21 instance ID | `nCJPZKPWsD8eaC_Hi0cue` |
| AQ22 instance ID | `J2nMHiuaofvDZ7if9HfoC` |
| AQ21 IP | `192.168.105.21` |
| AQ22 IP | `192.168.105.22` |
| Companion module | `analogway-livepremier` |
| Action | `/api/tpp/v1/load-master-memory` |
| Preset index key | `memoryId` (integer) |
| Action target | `preview` |
| Stream Deck | XL (8 cols × 4 rows) |

---

## Companion Page Map

| Page | Content | Notes |
|------|---------|-------|
| 1 | Show Day 1 | ~8 artists, some with multiple presets |
| 20 | Show Day 2 | same structure |
| 40 | Show Day 3 | same structure |
| 60 | Companion Controller | nav/utility buttons |
| 80 | Emergency | emergency presets |
| 90+ | Router Control | router pages |

Every page must have **page up**, **page down**, and **page number** nav buttons.
Confirmed grid positions (from reference config):

| Button | Row | Col |
|--------|-----|-----|
| pageup | 2 | 7 |
| pagenum | 3 | 6 |
| pagedown | 3 | 7 |

These positions are hardcoded in `companion_updater.NAV_POSITIONS` and are
always skipped when stamping preset buttons.

---

## Tool 1 — Companion Sync

**Status:** ✅ Code complete. Needs on-device validation.

### Phase 1 — Confirm LivePremier API  ✅ COMPLETE

Confirmed endpoints on live device (AQL C+, firmware 6.0.6):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stores/device` | GET | Full device state — memories, outputs, MVs, inputs |
| `/api/tpp/v1/system` | GET | Device info (model, firmware) |
| `/api/tpp/v1/inputs` | GET | Input list |
| `/api/tpp/v1/screens` | GET | Screen list |
| `/api/tpp/v1/multiviewers` | GET | Multiviewer list |
| `/api/tpp/v1/load-master-memory` | POST | Load a master memory |

Memory path: `device.masterPresetBank.bankList.items[id].control.pp.label` (name),
`.status.pp.isValid` (True = programmed slot). No authentication required.

`src/common/aquilon_comms.py` is fully implemented and smoke-tested.

### Phase 2 — Button Placement  ✅ COMPLETE

Three placement modes, all configurable in `config.toml`:

**Auto-flow** — `memory_ids` fill left-to-right, top-to-bottom, skipping nav and pinned positions.

**Pinned** — specific presets at exact row/col. Per-button overrides for `color`,
`text_color`, `text_size`. Pinned positions are skipped by auto-flow.

**Template buttons** — reusable non-preset buttons defined in `[[companion.button_templates]]`
and placed by name in any page's `buttons` list. Per-placement overrides are merged on top.
Supported actions: `"screen-take"` (fires on both AQ instances), `"label"` (no-action reminder).

### Phase 3 — Smart Text Sizing  ✅ COMPLETE

`smart_wrap = true` in `config.toml` enables automatic font size step-down for "auto" buttons.
Word-wrap simulation: wraps at spaces; a mid-word break only occurs when a single word exceeds
the character width for that size. Steps down through `["30", "24", "18", "14", "7"]` until
the label fits cleanly. Explicit `text_size` values are always passed through unchanged.

Calibrated constants in `companion_updater.py`:
```python
CHARS_PER_LINE = {"30": 5, "24": 5, "18": 7, "14": 12, "7": 17}
MAX_LINES      = {"30": 2, "24": 2, "18": 2, "14": 4,  "7": 8}
```

### Phase 4 — Nav Buttons  ✅ COMPLETE

Nav button positions confirmed and hardcoded in `companion_updater.NAV_POSITIONS`.
`apply_presets_to_page()` preserves nav buttons when clearing a page and skips
their positions when placing presets.

### Phase 5 — End-to-End Test  ⏳ PENDING

1. `pip install pyyaml python-dotenv`
2. `cp config.example.toml config.toml` — fill in page mappings
3. `cp .env.example .env` — fill in AQ IPs
4. `python src/companion_sync/main.py`
5. Import `outputs/updated.companionconfig` into Companion
6. Press buttons, confirm correct presets fire on AQ21 + AQ22

---

## Tool 2 — MV Setup

**Status:** ✅ Fully implemented. Needs on-device validation.

### Scope
Build multiviewer window layouts on Aquilon outputs. Sources include all
inputs plus program/preview. Layout changes per show — config-driven via
`mv_config.toml`.

### Design

Named layout presets in `mv_config.toml`:

```toml
[[layouts]]
name     = "all_inputs"
mv_id    = 1
canvas_w = 1920
canvas_h = 1080

[[layouts.windows]]
widget_id   = 1
source_type = "input"   # "input" | "screen-program" | "screen-preview" | "timer" | "image" | "none"
source_id   = 1
x = 0
y = 0
w = 320
h = 270
```

Run with: `python src/mv_setup/main.py --config mv_config.toml --layout all_inputs`

### API

- **Source assignment:** REST `set_mv_widget_source()` — assigns source type + ID
- **Geometry:** AWJ WebSocket `set_mv_widget_geometry()` — sets position + size in one batch
- **Enable/disable:** AWJ WebSocket `set_mv_widget_enabled()`
- **Save MV memory:** AWJ WebSocket `save_mv_memory()` — writes label + triggers save in one session

### Capture / Restore

```bash
# Snapshot live device → TOML
python src/mv_setup/capture.py --out mv_config.toml

# Restore all MV memories from TOML → device
python src/mv_setup/restore.py --config mv_config.toml
python src/mv_setup/restore.py --config mv_config.toml --dry-run
```

A real captured config (`coachella_mv_config.toml`, 36 layouts) is included in the repo.

### Phase 3 — Test on device  ⏳ PENDING

Apply a layout, verify on the MV output monitor.

---

## Tool 3 — AQ Backup Verify

**Status:** ✅ Code complete. Needs on-device validation.

### Purpose
Verify AQ22 (backup) matches AQ21 (primary) across five categories.
Read-only — does not modify either unit.

### What is verified

| Check | Details |
|-------|---------|
| System info | Firmware version + device type |
| Inputs | IDs and labels |
| Screens | IDs, labels, enabled state |
| Outputs | IDs, labels, output formats |
| Master Memories | IDs, names, count; no extras on either unit |

Each check reports pass/fail independently. Tool exits non-zero if any check fails.

### Phase 2 — Test on device  ⏳ PENDING

Run against both live units. Confirm system info JSON field names (`firmware`,
`deviceType`) match actual API response. See `tests/test_aq_backup_verify.py`.

---

## Testing

Zero margin for error on preset triggers. Every generated config must be verified.

### What is verified

| Check | How |
|-------|-----|
| Correct `memoryId` per button | Assert action options match the AQ memory that generated the button |
| Button label == memory name | Assert `style.text` == AQ-returned name, character for character |
| Both AQ instances on every button | Assert every preset button's `down` list has exactly one action per instance |
| Nav buttons on every page | Assert `pageup`, `pagedown`, `pagenum` buttons exist at correct positions |
| Nav positions never overwritten | Assert no preset button occupies a reserved nav slot |

### Test suite (`tests/`)

```
tests/
  conftest.py              — live AQ fixture, sample config fixtures
  test_companion_sync.py   — end-to-end: generate config → verify all checks
  test_aq_comms.py         — verify AQ API responses parse correctly
  test_aq_backup_verify.py — verify AQ21 and AQ22 match across all checks
```

Tests run against a **live Aquilon** — no mocking. Requires the AQ to be
reachable at the host configured in `.env`. Tests are automatically skipped
if `.env` variables are missing.

```bash
pytest tests/ -v
pytest tests/test_companion_sync.py::TestPresetButtons -v  # single class
```

---

## How to Run

```bash
# Setup (once)
python -m venv .venv
source .venv/bin/activate
pip install pyyaml python-dotenv
pip install -e ".[dev]"   # optional, adds pytest

cp .env.example .env
cp config.example.toml config.toml
cp mv_config.example.toml mv_config.toml
# Edit .env with AQ IPs, config.toml with page mappings

# Tool 1 — Companion preset sync (re-run any time presets change)
python src/companion_sync/main.py
# → import outputs/updated.companionconfig into Companion

# Tool 2 — MV layout
python src/mv_setup/main.py --config mv_config.toml --layout <name>
python src/mv_setup/main.py --config mv_config.toml --list

# Tool 3 — Verify backup matches primary
python src/aq_backup_verify/main.py
```

---

## Protocol Notes

### LivePremier REST API

- **Base URL:** `http://<host>/api/tpp/v1/`
- **Dev/testing:** `127.0.0.1:3003` (accepts connections; does NOT process AWJ WebSocket writes)
- **Show (on-site):** update `.env` with the actual IPs
- **Auth:** None required

### LivePremier AWJ WebSocket

- **URL:** `ws://<host>/api/ws/v1/awj`
- Used for all SET writes (geometry, labels, save triggers)
- `ws_send_batch([(path, value), ...])` — sends multiple SETs in one persistent session

### Companion Action (confirmed)

```yaml
action: /api/tpp/v1/load-master-memory
instance: <instance_id>
options:
  memoryId: <int>
  target: preview
```
