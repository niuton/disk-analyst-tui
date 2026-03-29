# disk-analyst-tui

TUI system manager for macOS — disk analysis, smart cleanup, and package management.

Built with [Textual](https://textual.textualize.io/).

## Features

- **Dashboard** — disk usage overview, package stats with total sizes
- **Disk Explorer** — directory tree with sizes, large file finder, cleanup wizard
- **Package Manager** — browse Homebrew, npm global, and pip packages sorted by size
- **Smart Cleanup** — auto-clean safe targets (.DS_Store, __pycache__, caches), confirm for larger items

## Install

```bash
# From PyPI
pip install disk-analyst-tui

# From Homebrew
brew install niuton/tap/disk-analyst-tui
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

| Key | Action |
|-----|--------|
| `1` `2` `3` | Switch tabs |
| `q` | Quit |
| `r` | Refresh |
| `Tab` | Navigate |

## Requirements

- macOS
- Python 3.11+
- Homebrew (for brew package listing)

## License

MIT
