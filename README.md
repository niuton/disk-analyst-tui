# disk-analyst-tui

TUI system manager for macOS — disk analysis, smart cleanup, package management, and Docker cleanup.

Built with [Textual](https://textual.textualize.io/).

## Features

### Dashboard
- Disk usage bar with color-coded alerts (70%+ warning, 85%+ critical)
- Package overview: total count and size per manager (Homebrew, npm, pip)
- Grand total of all installed packages

### Disk Explorer
- Interactive directory tree with size annotations
- Large file finder (files > 1MB)
- Smart cleanup wizard:
  - **Auto-clean** safe targets: `.DS_Store`, `__pycache__`, `.pyc`, `Thumbs.db`, brew/pip/npm caches
  - **Confirm** before removing: `node_modules`, large log files

### Package Manager
- Browse Homebrew, npm global, and pip packages sorted by size
- Real disk size per package
- Search/filter packages by name
- Orphan detection (Homebrew)
- Uninstall packages with confirmation dialog

### Docker Manager
- List all Docker images with sizes
- List all containers with status
- Remove individual images or containers
- Prune all unused Docker resources (stopped containers, dangling images, build cache)
- Gracefully handles Docker not running

## Install

```bash
# Homebrew
brew tap niuton/tap
brew install disk-analyst-tui

# pip (from GitHub)
pip install git+https://github.com/niuton/disk-analyst-tui.git

# From source
git clone https://github.com/niuton/disk-analyst-tui.git
cd disk-analyst-tui
pip install .
```

## Usage

```bash
# Launch TUI
disk-analyst

# CLI mode
disk-analyst scan /path      # Scan directory sizes
disk-analyst cleanup         # Run cleanup wizard
disk-analyst packages        # List all packages with sizes
```

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| `1` | Dashboard tab |
| `2` | Disk tab |
| `3` | Packages tab |
| `4` | Docker tab |
| `q` | Quit |
| `r` | Refresh |
| `Tab` | Navigate between widgets |

### Packages Tab

| Key | Action |
|-----|--------|
| `/` | Focus search bar |
| `Esc` | Clear search |
| `d` | Uninstall selected package |
| `Up/Down` | Navigate package list |

### Docker Tab

| Key | Action |
|-----|--------|
| `d` | Remove selected image/container |
| `p` | Prune all unused Docker resources |
| `Up/Down` | Navigate list |

## Architecture

```
disk_analyst_tool/
├── core/               # Engine (no TUI dependency)
│   ├── models.py       # Pydantic data models
│   ├── disk.py         # Disk scanning & usage
│   ├── cleanup.py      # Smart cleanup detection & execution
│   ├── packages.py     # Homebrew/npm/pip queries with sizes
│   └── docker.py       # Docker image/container management
├── tui/                # Textual TUI
│   ├── app.py          # Main app with 4 tabs
│   ├── styles.tcss     # Theme & layout
│   └── screens/        # Dashboard, Disk, Packages, Docker
└── cli.py              # CLI entry point
```

The core library is independent of the TUI — it can be consumed by other tools, scripts, or a future Claude Code plugin.

## Requirements

- macOS
- Python 3.11+
- Homebrew (for brew package listing)
- Docker (optional, for Docker tab)

## License

MIT
