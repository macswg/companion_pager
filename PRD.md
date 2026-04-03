# Product Requirements Document — Aquilon Show Control Toolkit

## Overview

A collection of three independent Python tools for show prep with the Analog Way
LivePremier (Aquilon) and Bitfocus Companion. Each tool serves a distinct stage
of setup and should not be confused with the others.

| Tool | Purpose | Run when |
|------|---------|----------|
| **Companion Sync** | Pull AQ preset names → Companion buttons | After presets are named on AQ (re-runnable) |
| **MV Setup** | Build multiviewer window layouts on AQ outputs | Show build |
| **AQ Backup Verify** | Verify AQ22 firmware + memories match AQ21 | On demand, after any significant change to AQ21 |

---

## Hardware

| Item | Detail |
|------|--------|
| Aquilon units | Two (AQ21 @ `192.168.105.21`, AQ22 @ `192.168.105.22`) |
| AQ relationship | Matched pair — identical `memoryId` fired on both simultaneously |
| Stream Deck | XL (8 cols × 4 rows) |
| Companion module | `analogway-livepremier` |
| REST API | `http://<host>/api/tpp/v1/` (dev: `127.0.0.1:3003`) |
| AWJ WebSocket | `ws://<host>/api/ws/v1/awj` — used for all SET writes |

---

## Tool 1 — Companion Sync

### Purpose
Query Master Memory names and IDs from the LivePremier and stamp them onto
Companion buttons, organized by show day and category.

### Companion Page Map

| Page | Content |
|------|---------|
| 1 | Friday Show (1) — show day presets |
| 2 | Sat Show (2) — show day presets |
| 3 | Sunday Show (3) — show day presets |
| 18 | LW x48 Salvos — cleared each run |
| 20 | Setup Presets (20) — test patterns, pixel map presets; `clear=false` |
| 21–25 | Presets (21)–(25) — AQ presets 1–90 |
| 26–29 | (reserved) — cleared each run |
| 50 | Page Control (50) — navigation, clock, utility buttons; `clear=false` |
| 80 | Emergency |

### Navigation Buttons
Every page must have three reserved navigation buttons:
- **Page Up** — row 2, col 7
- **Page Number** — row 3, col 6
- **Page Down** — row 3, col 7

These buttons must not be overwritten by preset stamps. Positions are confirmed
from the reference config and hardcoded in `companion_updater.NAV_POSITIONS`.

### Button Placement

Two placement modes can be mixed on the same page:

**Auto-flow** — `memory_ids` list fills left-to-right, top-to-bottom, skipping
nav and pinned positions:
```toml
[[companion.pages]]
page_num   = 1
page_title = "Day 1"
color      = 0x003300
memory_ids = [100, 101, 102, 103]
```

**Pinned** — specific presets placed at exact row/col positions (skipped by auto-flow):
```toml
buttons = [
    { memory_id = 76, row = 2, col = 1, text_color = 0xCCCC00, text_size = "14" },
    { memory_id = 51, row = 2, col = 5, color = 0x330000 },
]
```

**Template buttons** — reusable non-preset buttons (TAKE, reminder labels) defined
once in `[[companion.button_templates]]` and placed by name on any page:
```toml
[[companion.button_templates]]
name      = "take"
action    = "screen-take"
screen_id = 1
label     = "TAKE"
color     = 0x9D0101

# In a page's buttons list:
buttons = [
    { template = "take", row = 2, col = 6 },
]
```

Supported template actions: `"screen-take"` (fires on both AQ instances), `"label"` (no-action reminder),
`"page-jump"` (Companion `set_page`; supports static device serials and `$(variables)` for controller),
`"preset"` (fires `load-master-memory` for a fixed `memory_id`).

**Inline action buttons** — `action` field can be used directly in a page's `buttons` list without defining a named template.

**`clear = false`** — per-page option that skips the wipe step, allowing complex buttons from the template config to pass through unmodified.

### Per-Button Overrides

All buttons (auto-flow and pinned) support:
- `color` — background color (default: page color)
- `text_color` — label text color (default: white `0xFFFFFF`)
- `text_size` — font size: `"auto"`, `"7"`, `"14"`, `"18"`, `"24"`, `"30"` (default: `"auto"`)

### Smart Text Sizing (`smart_wrap`)

When `smart_wrap = true` in `config.toml`, auto-sized buttons are stepped down
through font sizes until the label wraps cleanly at word boundaries. A mid-word
break is only possible when a single word exceeds the character width for that size.
Explicit `text_size` values are always respected unchanged.

### Button Style
- Buttons are color-coded by page/category (each show day page gets a distinct color).
- Both AQ instances fire the same `memoryId` (two action entries per button).
- Action target: `preview`.

### Re-runnability
The sync tool must be safely re-runnable at any point during show prep. Running
it multiple times overwrites the previous output — it does not accumulate changes.

---

## Tool 2 — MV Setup

### Purpose
Configure multiviewer window layouts on Aquilon outputs. The layout changes
per show, so the tool must be data-driven and easy to update.

### Scope
- Position and size MV windows across one or more outputs
- Assign sources to windows (all inputs + program/preview)
- Support multiple named MV layout presets
- Capture existing device layouts to a portable TOML config
- Restore all MV memories from a TOML config to a device

### Data Source
Layout parameters are defined in `mv_config.toml` as named layout presets. The
script applies a chosen layout to the AQ. Layouts can also be captured from a
live device with `capture.py` and restored with `restore.py`.

### Flexibility
Layout changes happen in config only — no Python code changes needed between shows.

---

## Tool 3 — AQ Backup Verify

### Purpose
Verify that AQ22 (backup) matches AQ21 (primary). Run on demand any time you
want to confirm the backup is in sync before or during a show.

### What is verified
1. **System info** — firmware version and device type match
2. **Inputs** — same IDs and labels on both units
3. **Screens** — same IDs, labels, and enabled state
4. **Outputs** — same IDs, labels, and output formats
5. **Master Memories** — same IDs, names, and count; no extras on either unit

### Data source
No config file needed — the tool reads directly from both units.
Host IPs come from `.env` (`AQ_PRIMARY_HOST`, `AQ_BACKUP_HOST`).

### Error handling
The tool reports each check individually as pass/fail and exits non-zero if any
check fails, so the operator knows exactly what's out of sync.

---

## Testing Requirements

There is zero margin for error on preset triggers. Every generated Companion
config must be verified before it goes on-site.

### What must be verified (every run)

| Check | Description |
|-------|-------------|
| **Correct memoryId** | Every button's action `options.memoryId` matches the AQ memory it represents |
| **Label matches name** | Button `style.text` exactly matches the AQ memory name as returned by the API |
| **Both instances wired** | Every preset button has two `down` actions — one for AQ21, one for AQ22 (uses `definitionId`/`connectionId` format) |
| **Nav buttons present** | Every generated page has page up, page down, and page number buttons at correct positions |
| **Nav never overwritten** | No preset button is stamped onto a nav button slot |

### Approach

- **Test suite:** `pytest` tests run against a live Aquilon (no mocking). Tests
  query the real device, generate a config, and assert all checks above pass.
- **Built-in verification:** `main.py` logs warnings for any `memory_ids` not found
  on the device and exits with a non-zero status on connection failure. The
  `pytest` test suite (`test_companion_sync.py`) performs the post-generation
  verification pass against a live Aquilon.

### Test suite location: `tests/`

```
tests/
  test_companion_updater.py — offline unit tests (66 tests, no live AQ required)
  test_companion_sync.py    — verifies generated Companion config correctness (live AQ)
  test_aq_comms.py          — verifies AQ API responses parse correctly (live AQ)
  test_aq_backup_verify.py  — verifies AQ21 and AQ22 match across all checks (live AQ)
  conftest.py               — shared fixtures (live AQ connection, sample configs)
```

### Running tests

```bash
# Requires live AQ on the network
pytest tests/ -v
pytest tests/test_companion_sync.py::TestPresetButtons -v  # single class
```

---

## Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | MV Setup: needs on-device validation of geometry + save | ⏳ Pending live test |
| 2 | Companion Sync: needs end-to-end on-device validation | ⏳ Pending live test |
| 3 | AQ Backup Verify: confirm system info JSON field names on real device | ⏳ Pending live test |
