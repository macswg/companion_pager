# Implementation Plan — Aquilon Show Control Toolkit

## Tools in this Repo

Each tool is independent. They share a common REST client but are run at
different stages of show prep.

| Tool | Entry Point | Purpose | Stage |
|------|-------------|---------|-------|
| **Companion Sync** | `src/companion_sync/main.py` | AQ preset names → Companion buttons | After presets named |
| **AQ Setup** | `src/aq_setup/main.py` | Configure AQ outputs (resolution, connector, colorspace) | Show build |
| **MV Setup** | `src/mv_setup/main.py` | Configure multiviewer window layouts | After AQ outputs set |
| **AQ Clone** | `src/aq_clone/main.py` | Export AQ21 config → import to AQ22 → verify both match | On demand |

All tools share `src/common/aquilon_comms.py` as the LivePremier REST API client.
Each tool is independent — do not mix them up.

---

## Repo Structure

```
companion_pager/
├── config.example.toml              ← copy → config.toml (gitignored)
├── PRD.md / PLAN.md / README.md
├── pyproject.toml                   ← dependencies: pyyaml
├── example config files for ref/
│   └── nuc-green_2026_draft.companionconfig  ← 2025 show reference layout
├── src/
│   ├── companion_sync/              ← TOOL 1: Companion preset sync
│   │   ├── main.py
│   │   └── companion_updater.py
│   ├── aq_setup/                    ← TOOL 2: Aquilon output configuration
│   │   └── main.py
│   ├── mv_setup/                    ← TOOL 3: Multiviewer layout configuration
│   │   └── main.py
│   ├── aq_clone/                    ← TOOL 4: Clone AQ21 config → AQ22
│   │   └── main.py
│   └── common/                      ← shared (not a tool)
│       └── aquilon_comms.py
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
Their grid positions must be reserved and never overwritten by preset stamps.

TODO: Confirm exact row/col positions for nav buttons from reference config.

---

## Tool 1 — Companion Sync

**Status:** Core code complete. Three things still needed before it fully works.

### Phase 1 — Confirm LivePremier API  ← BLOCKER

1. Browse to `http://127.0.0.1:3003/api/tpp/v1/` and find the memories endpoint.
2. Confirm response schema (field names for memory ID and name).
3. Update `src/common/aquilon_comms.py` — all assumptions marked with `TODO`.

### Phase 2 — Grouping Config

Define the mapping from AQ memory IDs → Companion pages in `config.toml`:

```toml
[[companion.pages]]
page_num = 1
page_title = "Day 1"
color = 0x003300        # dark green
memory_ids = [1, 2, 3, 4, 5, 6, 7, 8]   # or a range: memory_id_range = [1, 20]

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

Update `src/companion_sync/main.py` to loop over pages and apply per-page color.

### Phase 3 — Nav Buttons

Confirm the grid positions of the page up / page down / page number buttons
from the reference config, then add logic to `companion_updater.py` to:
- Reserve those positions (skip them when stamping presets)
- Ensure every generated page has the correct nav buttons

### Phase 4 — End-to-End Test

1. `pip install pyyaml`
2. `cp config.example.toml config.toml` — fill in host and page mappings
3. `python src/companion_sync/main.py`
4. Import `outputs/updated.companionconfig` into Companion
5. Press buttons, confirm correct presets fire on AQ21 + AQ22

---

## Tool 2 — AQ Setup

**Status:** Stub only.

### Scope
Configure Aquilon outputs — run once per show build to ensure outputs match
the show spec. Applied identically to AQ21 and AQ22.

Settings to configure per output:
- Resolution (UHD 3840×2160, 1080p 1920×1080, etc.)
- Refresh rate (59.94, 29.97, etc.)
- Connector type (SDI, HDMI, DisplayPort)
- Colorspace / chroma / color range

### Phase 1 — Find AQ REST endpoints for output config

Inspect the `analogway-livepremier` Companion module or API docs to find:
- `GET` endpoint for reading current output settings
- `SET`/`PUT` endpoint for applying output settings

Reference: the existing reference config contains actions like `OSP` from the
old Spyder code — the LivePremier will have equivalent REST endpoints.

### Phase 2 — Implement

Add output config functions to `src/aq_setup/main.py`.
Drive all values from `config.toml`:

```toml
[aq_setup]
outputs = [
  { id = 0, resolution = "3840x2160", refresh = "59.94", connector = "SDI", colorspace = 2, chroma = 1 },
  { id = 1, resolution = "1920x1080", refresh = "59.94", connector = "HDMI", colorspace = 2, chroma = 1 },
]
```

### Phase 3 — Test on device

Apply to AQ21, verify settings, then apply to AQ22.

---

## Tool 3 — MV Setup

**Status:** Stub only.

### Scope
Build multiviewer window layouts on Aquilon outputs. Sources include all
inputs plus program/preview. Layout changes per show — must be config-driven.

### Design

Named layout presets in `config.toml`:

```toml
[[mv_setup.layouts]]
name = "tech_feed"
output_id = 2
windows = [
  { id = 0, source = "input_1", x = 0,    y = 0,   w = 640, h = 360 },
  { id = 1, source = "input_2", x = 640,  y = 0,   w = 640, h = 360 },
  { id = 2, source = "program", x = 1280, y = 0,   w = 640, h = 360 },
  # ...
]
```

Run with: `python src/mv_setup/main.py --layout tech_feed`

### Phase 1 — Find MV REST endpoints

Inspect the LivePremier API for:
- Window position/size endpoint
- Source assignment endpoint
- Titling endpoint

### Phase 2 — Implement

Add layout application logic to `src/mv_setup/main.py`.

### Phase 3 — Test on device

Apply a layout, verify on the MV output monitor.

---

## Tool 4 — AQ Clone

**Status:** Stub — API mechanism TBD.

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

### Phase 1 — Find the export/import API endpoints

The mechanism is unknown. To discover it:
- Browse `http://127.0.0.1:3003/api/tpp/v1/` for relevant endpoints
- Check for endpoints like `/config/export`, `/show/save`, `/backup`, etc.
- May be a file download (GET returns a binary/JSON blob) + file upload (POST)

### Phase 2 — Implement

```
src/aq_clone/
  main.py    ← orchestrates export → import → verify
```

Config needs both unit IPs:
```toml
[aquilon]
primary_host = "192.168.105.21"    # AQ21 — source of truth
backup_host  = "192.168.105.22"    # AQ22 — receives the clone
port = 80
```

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
```

Tests run against a **live Aquilon** — no mocking. Requires the AQ to be
reachable at the host configured in `config.toml`.

```bash
pytest tests/ -v
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
pip install pyyaml

cp config.example.toml config.toml
# Edit config.toml

# Tool 1 — Companion preset sync (re-run any time presets change)
python src/companion_sync/main.py
# → import outputs/updated.companionconfig into Companion

# Tool 2 — AQ output configuration (run at show build)
python src/aq_setup/main.py

# Tool 3 — MV layout (run after Tool 2)
python src/mv_setup/main.py
```

---

## Protocol Notes

### LivePremier REST API

- **Base URL:** `http://<host>/api/tpp/v1/`
- **Dev/testing:** `127.0.0.1:3003`
- **Show (on-site):** update `config.toml` with the actual IP
- **Memories endpoint:** TODO — assumed `GET /memories`
- **Auth:** TODO — assumed none

### Companion Action (confirmed)

```yaml
action: /api/tpp/v1/load-master-memory
instance: <instance_id>
options:
  memoryId: <int>
  target: preview
```
