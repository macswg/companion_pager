# Product Requirements Document — Aquilon Show Control Toolkit

## Overview

A collection of three independent Python tools for show prep with the Analog Way
LivePremier (Aquilon) and Bitfocus Companion. Each tool serves a distinct stage
of setup and should not be confused with the others.

| Tool | Purpose | Run when |
|------|---------|----------|
| **Companion Sync** | Pull AQ preset names → Companion buttons | After presets are named on AQ (re-runnable) |
| **AQ Setup** | Configure Aquilon outputs (resolution, connector, colorspace) | Show build, before doors |
| **MV Setup** | Build multiviewer window layouts on AQ outputs | Show build, after outputs are configured |
| **AQ Clone** | Export config from AQ21, import to AQ22, verify both match | On demand, after any significant change to AQ21 |

---

## Hardware

| Item | Detail |
|------|--------|
| Aquilon units | Two (AQ21 @ `192.168.105.21`, AQ22 @ `192.168.105.22`) |
| AQ relationship | Matched pair — identical `memoryId` fired on both simultaneously |
| Stream Deck | XL (8 cols × 4 rows) |
| Companion module | `analogway-livepremier` |
| API | LivePremier REST at `http://<host>/api/tpp/v1/` (dev: `127.0.0.1:3003`) |

---

## Tool 1 — Companion Sync

### Purpose
Query Master Memory names and IDs from the LivePremier and stamp them onto
Companion buttons, organized by show day and category.

### Companion Page Map

| Page | Content |
|------|---------|
| 1 | Show Day 1 — artist presets (~8 artists, some with multiple presets) |
| 20 | Show Day 2 — artist presets |
| 40 | Show Day 3 — artist presets |
| 60 | Companion Controller |
| 80 | Emergency |
| 90+ | Router control |

### Navigation Buttons
Every page must have three reserved navigation buttons:
- **Page Up** — goes to next page
- **Page Down** — goes to previous page
- **Page Number** — displays current page number

These buttons must not be overwritten by preset stamps. Their positions match
the Companion `pageup`, `pagedown`, and `pagenum` button types. Exact grid
positions TBD (confirm from reference config).

### Preset Organization
- Presets are pulled from the AQ and assigned to pages via a **grouping config**
  defined in `config.toml`.
- The grouping config maps memory ID ranges (or name patterns) to a Companion page
  number and title.
- AQ has more total memories than Companion has buttons — only the memories listed
  in the grouping config appear in Companion.
- AQ memory numbering mirrors the Companion page numbering as closely as possible.

### Button Style
- Buttons are color-coded by page/category (each show day page gets a distinct color).
- Both AQ instances fire the same `memoryId` (two action entries per button).
- Action target: `preview`.

### Re-runnability
The sync tool must be safely re-runnable at any point during show prep. Running
it multiple times overwrites the previous output — it does not accumulate changes.

---

## Tool 2 — AQ Setup

### Purpose
Script-driven configuration of the Aquilon outputs. Replaces manual menu
navigation for settings that need to be consistent show-to-show.

### Scope
- **Output resolution** — UHD (3840×2160), 1080p, etc.
- **Connector type** — SDI, HDMI, DisplayPort, etc.
- **Colorspace / chroma** — colorspace, chroma subsampling, color range

### Data Source
All configuration values come from `config.toml`. No data is pulled from the
AQ itself for this tool — values are set, not read.

### Applied to
Both AQ21 and AQ22 (same settings applied to both).

---

## Tool 3 — MV Setup

### Purpose
Configure multiviewer window layouts on Aquilon outputs. The layout changes
per show, so the tool must be data-driven and easy to update.

### Scope
- Position and size MV windows across one or more outputs
- Assign sources to windows (all inputs + program/preview)
- Set window titling
- Support multiple named MV layout presets (e.g. "tech feed", "confidence", "FOH")

### Data Source
Layout parameters (window count, grid dimensions, spacing, source assignments)
are defined in `config.toml` as named layout presets. The script applies a
chosen layout to the AQ.

### Flexibility
The tool must make it easy to adjust layouts between shows without touching
Python code — layout changes happen in config only.

---

## Tool 4 — AQ Clone

### Purpose
Export the full config from AQ21 (primary) and import it to AQ22 (backup),
then verify both units are in sync. Run on demand any time AQ21 changes
significantly and the backup needs to match.

### Steps
1. **Export** — trigger a config/show-file export from AQ21 via the REST API
2. **Import** — push that exported config to AQ22 via the REST API
3. **Verify** — query the memory list from both units and assert they are identical:
   - Same memory IDs
   - Same memory names
   - Same count

### Data source
No config file needed — the tool reads directly from AQ21 and writes to AQ22.
Host IPs for both units come from `config.toml`.

### Error handling
If the import or verification fails, the tool must exit with a clear error message
and a non-zero status. AQ22 must never be left in an ambiguous state silently.

### API mechanism
TBD — the LivePremier API mechanism for full config export/import needs to be
confirmed on-device. May be a dedicated endpoint, a file download/upload, or
an OS-level config file copy.

---

## Testing Requirements

There is zero margin for error on preset triggers. Every generated Companion
config must be verified before it goes on-site.

### What must be verified (every run)

| Check | Description |
|-------|-------------|
| **Correct memoryId** | Every button's action `options.memoryId` matches the AQ memory it represents — no off-by-one, no swapped IDs |
| **Label matches name** | Button `style.text` exactly matches the AQ memory name as returned by the API |
| **Both instances wired** | Every preset button has two `down` actions — one for AQ21, one for AQ22. No button fires only one unit |
| **Nav buttons present** | Every generated page has page up, page down, and page number buttons at their correct grid positions |
| **Nav never overwritten** | No preset button is stamped onto a nav button slot |

### Approach

- **Test suite:** `pytest` tests run against a live Aquilon (no mocking). Tests
  query the real device, generate a config, and assert all checks above pass.
- **Built-in verification:** After generating the config, `main.py` automatically
  runs a full verification pass on the output file and prints a pass/fail summary
  to the terminal before exiting. If any check fails, the run exits with a
  non-zero status and the output file should be considered invalid.

### Test suite location: `tests/`

```
tests/
  test_companion_sync.py   — verifies generated Companion config correctness
  test_aq_comms.py         — verifies AQ API responses parse correctly
  conftest.py              — shared fixtures (live AQ connection, sample configs)
```

### Running tests

```bash
# Requires live AQ on the network
pytest tests/ -v
```

---

## Open Questions

| # | Question | Status |
|---|----------|--------|
| 1 | Exact REST endpoint for listing Master Memories? | TODO — needs on-device check |
| 2 | Response JSON schema for memories list? | TODO |
| 3 | Does the API require authentication? | TODO |
| 4 | Exact grid positions for page up/down/num nav buttons? | TODO — check reference config |
| 5 | Which Stream Deck button positions are reserved for nav on each page? | TODO |
| 6 | MV REST endpoints for setting window position/size/source? | TODO |
| 7 | AQ output config REST endpoints? | TODO |
