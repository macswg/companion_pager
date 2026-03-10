# Aquilon Show Control Toolkit

Python tools for show prep with the Analog Way LivePremier (Aquilon) and Bitfocus
Companion. Automates output configuration, multiviewer layout, unit cloning, and
Companion button sync — tasks that would otherwise require manual setup on every
show build.

Each tool is independent. Use the right one for the right stage of setup.

---

## Tools

### Tool 1 — Companion Preset Sync
**`src/companion_sync/main.py`**

Queries Master Memory names and IDs from the LivePremier and stamps them onto
Stream Deck buttons in a Companion config. Run this after presets are finalized
on the Aquilon so button labels and action indexes stay in sync.

**Use for:** Updating Companion button labels and preset indexes.
**Does not touch:** The Aquilon device itself.

```bash
python src/companion_sync/main.py
```

---

### Tool 2 — MV Setup
**`src/mv_setup/main.py`**

Applies a named multiviewer layout to the Aquilon: window positions, sizes, and
source assignments (inputs, program bus, preview bus). Layouts are defined in a
separate TOML file so multiple configs can coexist for different shows or days.

**Use for:** Building the multiviewer layout on Aquilon outputs.
**Does not touch:** Companion configs or device presets.

MV layouts live in their own config file — keep one per show:

```bash
# Copy the example to get started
cp mv_config.example.toml mv_config.toml

# Or capture all MV memories from a live Aquilon into a named file
# (see "Capturing MV layouts" below)

# List available layouts in a config file
python src/mv_setup/main.py --config coachella_mv_config.toml --list

# Apply a layout
python src/mv_setup/main.py --config coachella_mv_config.toml --layout 10_mv_all_pgm_bot
```

#### Capturing MV layouts from a live Aquilon

To snapshot all MV memories from a programmed device and save them as a
portable config file, run the capture script:

```bash
python src/mv_setup/capture.py --out coachella_mv_config.toml
```

This reads every programmed MV memory from the device and writes a TOML file
with one `[[layouts]]` block per memory. The resulting file can be checked in
and used to restore layouts on any Aquilon.

#### Restoring MV layouts to a new Aquilon

To push all memories from a captured config file back to a device, run the
restore script:

```bash
python src/mv_setup/restore.py --config coachella_mv_config.toml
```

For each `[[layouts]]` block the script:
1. Applies the window layout to the live MV output (sources, positions, sizes)
2. Sets the memory slot label
3. Triggers an in-device save so the layout is stored in the bank

Preview what will happen without touching the device:

```bash
python src/mv_setup/restore.py --config coachella_mv_config.toml --dry-run
```

Layout names must start with the slot number followed by an underscore
(e.g. `01_inputs`, `10_mv_all_pgm_bot`).  Files produced by `capture.py`
always follow this format.

#### Layout config format

```toml
[[layouts]]
name     = "all_inputs"   # used with --layout
mv_id    = 1              # which MV output (1-based)
canvas_w = 1920           # MV canvas size in pixels
canvas_h = 1080

[[layouts.windows]]
widget_id   = 1           # window slot (1-based)
source_type = "input"     # input | screen-program | screen-preview | image | none
source_id   = 1           # source number (1-based); omit for "none"
x = 0                     # position and size in canvas pixels
y = 0
w = 320
h = 270
```

#### Companion config format

Buttons are defined per-page in `config.toml`. Two placement modes can be mixed freely on the same page:

**Auto-flow** — presets fill left-to-right, top-to-bottom, skipping nav slots:
```toml
[[companion.pages]]
page_num   = 1
page_title = "Friday Show (1)"
color      = 0x000000
memory_ids = [100, 101, 102, 103, 104, 105]
```

**Pinned** — place a specific preset at an exact row/col position. Pinned positions are skipped by auto-flow:
```toml
buttons = [
    { memory_id = 76, row = 2, col = 1 },
    { memory_id = 68, row = 2, col = 3, color = 0x330000, text_color = 0xCCCC00, text_size = "14" },
]
```

**Template buttons** — reusable non-preset buttons (TAKE, reminder labels, etc.) defined once and placeable on any page:
```toml
[[companion.button_templates]]
name      = "take"
action    = "screen-take"
screen_id = 1
label     = "TAKE"
color     = 0x9D0101

[[companion.button_templates]]
name       = "must_off_interstitial"
action     = "label"
label      = "MUST OFF before -> Interstitial"
text_color = 0xFF00FF
show_topbar = false
```

Then reference by name in any page's `buttons` list. Per-placement overrides are supported:
```toml
buttons = [
    { template = "take", row = 0, col = 7 },
    { template = "must_off_interstitial", row = 1, col = 0 },
    { template = "take", row = 2, col = 7, color = 0x330000 },
]
```

Supported template actions: `"screen-take"` (fires on both AQ instances), `"label"` (no-action reminder button).

**Color reference:**
```
0xCCCC00  yellow text       0xFF0000  bright red text
0x9D0101  bright red bg     0x330000  dark red bg
0x003300  green bg          0xFF00FF  purple text
0xFFFFFF  white             0x000000  black
```

---

### Tool 3 — AQ Backup Verify
**`src/aq_backup_verify/main.py`**

Checks that AQ22 (backup) matches AQ21 (primary) — firmware version and Master
Memory lists. Run on demand any time you want to confirm the backup is in sync.

**Use for:** Verifying AQ22 matches AQ21 before a show.
**Does not touch:** Companion configs, output modes, or MV layouts.

```bash
python src/aq_backup_verify/main.py
```

---

## Show Prep Workflow

```
1. AQ Backup Verify → confirm AQ22 firmware and memories match AQ21
                      python src/aq_backup_verify/main.py

2. MV Setup         → apply multiviewer layout from config file
                      python src/mv_setup/main.py --config <file>.toml --layout <name>

3. Companion Sync   → pull preset names into Companion buttons
                      python src/companion_sync/main.py
                      → import outputs/updated.companionconfig into Companion

4. Test             → verify every button is correct
                      pytest tests/ -v
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install pyyaml python-dotenv

# IP addresses go in .env — never committed
cp .env.example .env
# Edit .env — set AQ_PRIMARY_HOST, AQ_BACKUP_HOST, AQ_PORT

# Everything else (page layout, file paths, output settings) goes in config.toml
cp config.example.toml config.toml
# Edit config.toml as needed

# MV layouts go in a separate file (one per show)
cp mv_config.example.toml mv_config.toml
# Or capture from a live device: python src/mv_setup/capture.py --out mv_config.toml
```

---

## Project Structure

```
src/
  companion_sync/         ← Tool 1: Companion preset sync
    main.py
    companion_updater.py
  mv_setup/               ← Tool 2: Multiviewer layout configuration
    main.py
    capture.py
    restore.py
  aq_backup_verify/               ← Tool 3: Verify AQ22 matches AQ21
    main.py
  common/                 ← Shared: LivePremier REST API client
    aquilon_comms.py

tests/
  conftest.py
  test_companion_sync.py
  test_aq_comms.py
  test_aq_backup_verify.py

example config files for ref/
  nuc-green_2026_draft.companionconfig  — 2025 show reference layout

outputs/              — generated Companion configs (gitignored)
logs/                 — log files (gitignored)
config.example.toml   — reference config (copy → config.toml)
mv_config.example.toml — reference MV layout config (copy → mv_config.toml)
coachella_mv_config.toml — captured Coachella MV memories (36 layouts)
PRD.md               — product requirements
PLAN.md              — implementation plan and status
```

---

## Status

| Tool | Status |
|------|--------|
| Companion Sync (`src/companion_sync/`) | Code complete; needs on-device validation |
| MV Setup (`src/mv_setup/`) | Implemented — applies layouts from `mv_config.toml` |
| AQ Backup Verify (`src/aq_backup_verify/`) | Complete — checks firmware + memory lists |
| Test suite (`tests/`) | Structure planned, implementation pending |

See `PLAN.md` for details.
