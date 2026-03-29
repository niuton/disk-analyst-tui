# disk-analyst-tui — System Manager Tool Design

**Date:** 2026-03-29
**Status:** Implemented
**Name:** disk-analyst-tui (originally "TidyMac", renamed during development)

## Overview

disk-analyst-tui is a Python TUI system manager for macOS that handles disk analysis, smart cleanup, package management (Homebrew, npm global, pip), and Docker resource management. Built with a core library + TUI architecture, designed to later integrate as a Claude Code plugin with MCP server.

## Architecture: Core Library + TUI

```
disk_analyst_tool/
├── core/         # Engine: disk scanner, cleanup, pkg manager, docker
├── tui/          # Textual app — consumes core
└── cli.py        # Entry point
```

The core engine exposes a Python API. The TUI renders it. The CLI provides non-interactive access.

## Core Engine (`disk_analyst_tool/core/`)

### `models.py` — Pydantic Data Models

- `FileInfo` — path, size, modified date
- `DiskTree` — recursive tree node with children and aggregated size
- `DiskUsage` — total, used, free, percent
- `CleanTarget` — path, category, size, safe (bool)
- `CleanResult` — targets cleaned, bytes freed, errors
- `Package` — name, version, size, manager, is_orphan

### `disk.py` — Disk Analysis

- `scan_directory(path) -> DiskTree` — recursive scan, returns tree with sizes
- `find_large_files(path, min_size) -> list[FileInfo]` — top N largest files
- `get_disk_usage() -> DiskUsage` — overall volume stats

### `cleanup.py` — Smart Cleanup

- `detect_cleanable(path) -> list[CleanTarget]` — finds caches, temp files, etc.
- `categorize_targets(targets) -> dict[str, list[CleanTarget]]` — "safe" vs "confirm"
- `clean(targets, dry_run=False) -> CleanResult` — executes cleanup
- `detect_caches() -> list[CleanTarget]` — system-level cache directories

**Safe auto-clean targets:** `.DS_Store`, `__pycache__`, `.pyc`, `Thumbs.db`, Homebrew cache, pip cache, npm cache

**Confirm-required targets:** `node_modules`, large log files, old downloads (>30 days)

### `packages.py` — Package Manager Queries

- `list_homebrew() -> list[Package]` — formulae + casks with real disk sizes
- `list_npm_global() -> list[Package]` — global npm packages with sizes
- `list_pip() -> list[Package]` — pip packages with sizes
- `uninstall(package) -> tuple[bool, str]` — remove with cleanup
- `find_orphans(manager) -> list[Package]` — packages not depended on

### `docker.py` — Docker Resource Management

- `is_docker_available() -> bool` — check if Docker is running
- `list_images() -> list[DockerImage]` — images with sizes, sorted by size desc
- `list_containers(all) -> list[DockerContainer]` — containers with status
- `list_volumes() -> list[DockerVolume]` — volumes
- `remove_image(image_id, force) -> tuple[bool, str]` — remove image
- `remove_container(container_id, force) -> tuple[bool, str]` — remove container
- `prune_all(include_volumes) -> DockerCleanResult` — docker system prune

## TUI (`disk_analyst_tool/tui/`)

Built with Textual. Four tabs:

### Dashboard (Tab 1)
- Disk usage progress bar with color-coded alerts (70%+ yellow, 85%+ red)
- Used/Total/Free disk stats
- Package overview table: count and total size per manager + grand total
- Async loading so UI never freezes

### Disk Explorer (Tab 2)
- Path input with Scan, Large Files, and Cleanup buttons
- Expandable directory tree with size annotations (max depth 3)
- Large files table (files > 1MB, top 20)
- Cleanup wizard: auto-cleans safe targets, notifies about items needing confirmation
- All operations run in background threads

### Package Manager (Tab 3)
- Tabbed sub-views: Homebrew | npm | pip (via ContentSwitcher)
- Table: Name, Version, Size, Orphan? — sorted by size descending
- Search/filter bar (`/` to focus, `Esc` to clear)
- Uninstall with modal confirmation dialog (`d` key)
- Total installed size summary
- Auto-focus tables on view switch for arrow key navigation

### Docker Manager (Tab 4)
- Images and Containers views (via ContentSwitcher)
- Images table: Repository, Tag, ID, Size, Created
- Containers table: Name, Image, Status, ID
- Remove individual items with confirmation (`d` key)
- Prune all unused resources (`p` key)
- Gracefully handles Docker not running

### Navigation
- Tab bar: `Dashboard | Disk | Packages | Docker`
- Number keys: `1` `2` `3` `4` to switch tabs
- Footer keybindings: `q` quit, `r` refresh
- Auto-focus on tables when switching tabs/views

## Project Structure

```
agent-tools-plugin/
├── disk_analyst_tool/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── disk.py
│   │   ├── cleanup.py
│   │   ├── packages.py
│   │   └── docker.py
│   ├── tui/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── screens/
│   │   │   ├── dashboard.py
│   │   │   ├── disk.py
│   │   │   ├── packages.py
│   │   │   └── docker.py
│   │   ├── widgets/
│   │   └── styles.tcss
│   └── cli.py
├── tests/
│   ├── test_models.py
│   ├── test_disk.py
│   ├── test_cleanup.py
│   ├── test_packages.py
│   └── test_docker.py
├── pyproject.toml
└── README.md
```

## Dependencies

- **textual** >= 0.80 — TUI framework
- **pydantic** >= 2.0 — data models
- **psutil** — disk/system stats
- **humanize** — human-readable file sizes

## Distribution

- **PyPI name:** disk-analyst-tui
- **CLI command:** disk-analyst
- **Homebrew:** `brew tap niuton/tap && brew install disk-analyst-tui`
- **GitHub:** https://github.com/niuton/disk-analyst-tui

## CLI Entry Points

```bash
disk-analyst              # Launch TUI
disk-analyst scan /path   # Quick scan (prints results, no TUI)
disk-analyst cleanup      # Run cleanup wizard
disk-analyst packages     # List all packages
```

## Testing

- 29 unit tests across 5 test files
- Core modules tested with mocked filesystem/subprocess
- Docker module tested with mocked command output

## Future: Claude Code Plugin (separate design)

- Slash commands: `/disk-scan`, `/cleanup`, `/list-apps`
- Dedicated agent for autonomous system investigation
- MCP server exposing core API as structured JSON tools
