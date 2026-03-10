# Implementation Plan — Aquilon Show Control Toolkit

## Tools in this Repo

Each tool is independent. They share a common REST client but are run at
different stages of show prep.

| Tool | Entry Point | Purpose | Stage |
|------|-------------|---------|-------|
| **Companion Sync** | `src/companion_sync/main.py` | AQ preset names → Companion buttons | After presets named |
| **MV Setup** | `src/mv_setup/main.py` | Configure multiviewer window layouts | Show build |
| **AQ Clone** | `src/aq_clone/main.py` | Export AQ21 config → import to AQ22 → verify both match | On demand |

All tools share `src/common/aquilon_comms.py` as the LivePremier REST + WebSocket API client.
Each tool is independent — do not mix them up.

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
│   ├── aq_clone/                    ← TOOL 3: Clone AQ21 config → AQ22
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

### Phase 2 — Grouping Config  ✅ COMPLETE

Mapping from AQ memory IDs → Companion pages is defined in `config.toml`:

```toml
[[companion.pages]]
page_num = 1
page_title = "Day 1"
color = 0x003300        # dark green
memory_ids = [1, 2, 3, 4, 5, 6, 7, 8]

[[companion.pages]]
page_num = 20
page_title = "Day 2"
color = 0x000033        # dark blue
memory_ids = [20, 21, 22, 23, 24, 25, 26, 27]

[[companion.pages]]
page_num = 40
page_title = "Day 3"
color = 0x330000        # dark red
memory_ids = [40, 41, 42, 43, 44, 45, 46, 47]
```

### Phase 3 — Nav Buttons  ✅ COMPLETE

Nav button positions confirmed and hardcoded in `companion_updater.NAV_POSITIONS`.
`apply_presets_to_page()` preserves nav buttons when clearing a page and skips
their positions when placing presets.

### Phase 4 — End-to-End Test  ⏳ PENDING

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

## Tool 3 — AQ Clone

**Status:** ⚠️ Stub — API mechanism TBD.

### Purpose
Export the full show config from AQ21, import it to AQ22, then verify both
units have identical memory lists. Run on demand after any significant change
to AQ21.

### Steps the tool performs
1. **Export** — call the LivePremier export API on AQ21 and capture the config payload
2. **Import** — push that payload to AQ22 via the import API
3. **Verify** — query memory lists from both units, assert they are identical:
   - Same number of memories
   - Same IDs
   - Same names, in the same order
4. Report pass/fail clearly. Exit non-zero on any failure.

### Phase 1 — Find the export/import API endpoints  ⏳ PENDING

The mechanism is unknown. To discover it:
- Browse `http://127.0.0.1:3003/api/tpp/v1/` for relevant endpoints
- Check for endpoints like `/config/export`, `/show/save`, `/backup`, etc.
- May be a file download (GET returns a binary/JSON blob) + file upload (POST)

### Phase 2 — Implement

```
src/aq_clone/
  main.py    ← orchestrates export → import → verify
```

Config: both unit IPs come from `.env` (`AQ_PRIMARY_HOST`, `AQ_BACKUP_HOST`).

### Phase 3 — Test

Run against both live units, verify memory lists match after clone.
Add to `tests/test_aq_clone.py`.

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
  test_aq_clone.py         — verify AQ21 and AQ22 memory lists are identical (stub)
```

Tests run against a **live Aquilon** — no mocking. Requires the AQ to be
reachable at the host configured in `.env`. Tests are automatically skipped
if `.env` variables are missing.

```bash
pytest tests/ -v
pytest tests/test_companion_sync.py::TestPresetButtons -v  # single class
```

### Built-in verification in `main.py`

After writing the output file, `main.py` reads it back and runs all checks
automatically. Prints a pass/fail summary to the terminal. Exits non-zero if
any check fails — the output file should be considered invalid in that case.

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
