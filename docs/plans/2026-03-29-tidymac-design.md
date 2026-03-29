# TidyMac — System Manager Tool Design

**Date:** 2026-03-29
**Status:** Approved
**Scope:** Core engine + TUI (plugin planned separately)

## Overview

TidyMac is a Python TUI system manager for macOS that handles disk analysis, smart cleanup, and package management (Homebrew, npm global, pip). Built with a core library + TUI architecture, designed to later integrate as a Claude Code plugin with MCP server.

## Architecture: Core Library + TUI

```
tidymac/
├── core/         # Engine: disk scanner, cleanup, pkg manager queries
├── tui/          # Textual app — consumes core
└── cli.py        # Entry point
```

The core engine exposes a Python API. The TUI renders it. Later, the Claude Code plugin (commands, agent, MCP server) will consume the same core API.

## Core Engine (`tidymac/core/`)

### `models.py` — Pydantic Data Models

- `FileInfo` — path, size, modified date
- `DiskTree` — recursive tree node with children and aggregated size
- `DiskUsage` — total, used, free, percent
- `CleanTarget` — path, category, size, safe (bool)
- `CleanResult` — targets cleaned, bytes freed, errors
- `Package` — name, version, size, manager, is_orphan

### `disk.py` — Disk Analysis & Monitoring

- `scan_directory(path) -> DiskTree` — recursive scan, returns tree with sizes
- `find_large_files(path, min_size) -> list[FileInfo]` — top N largest files
- `get_disk_usage() -> DiskUsage` — overall volume stats
- `watch_disk(threshold, callback)` — background monitor, fires when usage exceeds threshold

### `cleanup.py` — Smart Cleanup

- `detect_cleanable(path) -> list[CleanTarget]` — finds caches, temp files, etc.
- `categorize_targets(targets) -> dict[str, list[CleanTarget]]` — "safe" vs "confirm"
- `clean(targets, dry_run=False) -> CleanResult` — executes cleanup

**Safe auto-clean targets:** `.DS_Store`, `__pycache__`, `.pyc`, `thumbs.db`, Homebrew cache, pip cache, npm cache

**Confirm-required targets:** `node_modules`, large log files, old downloads (>30 days)

### `packages.py` — Package Manager Queries

- `list_homebrew() -> list[Package]` — formulae + casks with sizes
- `list_npm_global() -> list[Package]` — global npm packages
- `list_pip() -> list[Package]` — pip packages
- `uninstall(package, manager) -> Result` — remove with cleanup
- `find_orphans(manager) -> list[Package]` — packages not depended on

## TUI (`tidymac/tui/`)

Built with Textual. Three main screens via tabs:

### Dashboard (Home)
- Disk usage bar (color-coded)
- Top 5 space hogs
- Quick stats: total packages per manager
- Alert banner if disk > 85%

### Disk Explorer
- Expandable directory tree with size annotations
- Sort by size (default), name, modified date
- Large files table (filterable)
- Cleanup wizard: auto-cleans safe targets, prompts for rest

### Package Manager
- Tabbed sub-views: Homebrew | npm | pip
- Table: name, version, size
- Orphan detector highlights
- Uninstall with preview + confirm

### Navigation
- Tab bar: `Dashboard | Disk | Packages`
- Footer keybindings: `q` quit, `r` refresh, `d` delete, `?` help
- Dark mode default

## Project Structure

```
agent-tools-plugin/
├── tidymac/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── disk.py
│   │   ├── cleanup.py
│   │   └── packages.py
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── screens/
│   │   │   ├── dashboard.py
│   │   │   ├── disk.py
│   │   │   └── packages.py
│   │   ├── widgets/
│   │   └── styles.tcss
│   └── cli.py
├── tests/
│   ├── test_disk.py
│   ├── test_cleanup.py
│   └── test_packages.py
├── pyproject.toml
└── README.md
```

## Dependencies

- **textual** >= 0.80 — TUI framework
- **pydantic** >= 2.0 — data models
- **psutil** — disk/system stats
- **humanize** — human-readable file sizes

## CLI Entry Points

```bash
tidymac              # Launch TUI
tidymac scan /path   # Quick scan (prints results, no TUI)
tidymac cleanup      # Run cleanup wizard in terminal
tidymac packages     # List all packages
```

## Testing Strategy

- Unit tests on core modules with mocked filesystem/subprocess
- No TUI tests initially — test core, trust Textual

## Future: Claude Code Plugin (separate design)

- Slash commands: `/disk-scan`, `/cleanup`, `/list-apps`
- Dedicated agent for autonomous system investigation
- MCP server exposing core API as structured JSON tools
