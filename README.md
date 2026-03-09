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

### Tool 2 — AQ Setup
**`src/aq_setup/main.py`**

Configures the Aquilon device itself: create/update Master Memories, set output
modes, configure inputs, save device state.

**Use for:** Programming the Aquilon before a show.
**Does not touch:** Companion configs or multiviewer layouts.

```bash
python src/aq_setup/main.py
```

---

### Tool 3 — MV Setup
**`src/mv_setup/main.py`**

Configures multiviewer window layouts on Aquilon outputs: position and size MV
windows, assign sources, set titling.

**Use for:** Building the multiviewer layout on Aquilon outputs.
**Does not touch:** Companion configs or device presets.

```bash
python src/mv_setup/main.py
```

### Tool 4 — AQ Clone
**`src/aq_clone/main.py`**

Exports the full config from AQ21 (primary), imports it to AQ22 (backup), then
verifies both units have identical memory lists. Run on demand any time AQ21
changes and the backup needs to match.

**Use for:** Keeping AQ22 in sync with AQ21 after programming.
**Does not touch:** Companion configs, output modes, or MV layouts.

```bash
python src/aq_clone/main.py
```

---

## Show Prep Workflow

```
1. AQ Setup         → configure outputs on the Aquilon
                      python src/aq_setup/main.py

2. AQ Clone         → push AQ21 config to AQ22 and verify they match
                      python src/aq_clone/main.py

3. MV Setup         → build multiviewer layouts on Aquilon outputs
                      python src/mv_setup/main.py

4. Companion Sync   → pull preset names into Companion buttons
                      python src/companion_sync/main.py
                      → import outputs/updated.companionconfig into Companion

5. Test             → verify every button is correct
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
```

---

## Project Structure

```
src/
  companion_sync/         ← Tool 1: Companion preset sync
    main.py
    companion_updater.py
  aq_setup/               ← Tool 2: Aquilon output configuration
    main.py
  mv_setup/               ← Tool 3: Multiviewer layout configuration
    main.py
  aq_clone/               ← Tool 4: Clone AQ21 config to AQ22
    main.py
  common/                 ← Shared: LivePremier REST API client
    aquilon_comms.py

tests/
  conftest.py
  test_companion_sync.py
  test_aq_comms.py
  test_aq_clone.py

example config files for ref/
  nuc-green_2026_draft.companionconfig  — 2025 show reference layout

outputs/             — generated Companion configs (gitignored)
logs/                — log files (gitignored)
config.example.toml  — reference config (copy → config.toml)
PRD.md               — product requirements
PLAN.md              — implementation plan and status
```

---

## Status

| Tool | Status |
|------|--------|
| Companion Sync (`src/companion_sync/`) | Code complete; API endpoint needs on-device confirmation |
| AQ Setup (`src/aq_setup/`) | Stub only — scope defined, implementation pending |
| MV Setup (`src/mv_setup/`) | Stub only — scope defined, implementation pending |
| AQ Clone (`src/aq_clone/`) | Stub only — export/import API mechanism TBD |
| Test suite (`tests/`) | Structure planned, implementation pending |

See `PLAN.md` for details.
