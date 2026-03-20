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
│   ├── current_config_19Mar_m5mpb.local_2026-03-19-2031_custom_config.companionconfig  ← current show template
│   └── vars_m5mpb.local_2026-03-19-2229_custom_config.companionconfig                  ← reference for action formats
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

## Reference: Current Show Config

Key facts from `current_config_19Mar_m5mpb.local_2026-03-19-2031_custom_config.companionconfig`:

| Detail | Value |
|--------|-------|
| Companion version | 6 |
| Config format | YAML |
| AQ21 instance ID | `KOjlQky3o3GrhW5_r_7gS` |
| AQ22 instance ID | `0XMkeXvgqzbBUFtf_X2qL` |
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
| 1 | Friday Show (1) | show day presets, auto-flow + pinned template buttons |
| 2 | Sat Show (2) | same structure |
| 3 | Sunday Show (3) | same structure |
| 18 | LW x48 Salvos | cleared each run; content from template |
| 20 | Setup Presets (20) | test patterns + pixel map presets; `clear=false` |
| 21–25 | Presets (21)–(25) | AQ presets 1–90, 20 per page (rows 0–2 auto-flow, row 3 cols 0–1 pinned) |
| 26–29 | (reserved) | cleared each run |
| 50 | Page Control (50) | nav bar, clock, show day jumps, TAKE, EMER, OFF; `clear=false` |
| 80 | Emergency | emergency presets |

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
Supported actions: `"screen-take"` (fires on both AQ instances), `"label"` (no-action reminder),
`"page-jump"` (Companion internal `set_page`; `controller` accepts `"self"`, a static device serial, or a `$(variable)`),
`"preset"` (fires `load-master-memory` for a fixed `memory_id`; label from device unless overridden).

**Inline action buttons** — `action` field used directly in the `buttons` list without a named template.
`page-jump` and `label` are the most common inline uses.

**`clear = false`** — per-page flag that skips the wipe step so complex buttons in the template config
pass through unmodified. Only buttons explicitly listed in `buttons` are touched.

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

A captured config (`my_show_mv_config.toml`) can be generated with `capture.py` and used to restore all MV memories.

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
  conftest.py                  — live AQ fixture, sample config fixtures
  test_companion_updater.py    — offline unit tests (66 tests, no live AQ required)
  test_companion_sync.py       — end-to-end: generate config → verify all checks
  test_aq_comms.py             — verify AQ API responses parse correctly
  test_aq_backup_verify.py     — verify AQ21 and AQ22 match across all checks
```

`test_companion_updater.py` runs fully offline — no live AQ or `.env` required.
All other tests run against a **live Aquilon**. Tests are automatically skipped
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
python src/companion_sync/main.py --config other_config.toml  # alternate config
# → import outputs/updated_<timestamp>.companionconfig into Companion

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

### Companion Action format (Companion v6)

AQ preset / screen-take actions:
```yaml
- type: action
  id: <22-char id>
  definitionId: /api/tpp/v1/load-master-memory
  connectionId: <instance_id>
  options:
    memoryId: <int>
    target: preview
```

Internal page-jump action:
```yaml
- type: action
  id: <22-char id>
  definitionId: set_page
  connectionId: internal
  options:
    controller_from_variable: false   # true when controller is a $(variable)
    controller: self                  # or "streamdeck:CL37L2A00862"
    controller_variable: self         # or "$(custom:green_surface)"
    page_from_variable: false
    page: <int>
    page_variable: "1"
  children: {}
```
