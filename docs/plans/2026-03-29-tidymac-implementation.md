# TidyMac Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python TUI system manager for macOS that scans disk usage, performs smart cleanup, and manages Homebrew/npm/pip packages.

**Architecture:** Core library (`tidymac/core/`) exposes a Python API consumed by a Textual TUI (`tidymac/tui/`). Clean separation so a Claude Code plugin can later consume the same core.

**Tech Stack:** Python 3.11+, Textual (TUI), Pydantic (models), psutil (system stats), humanize (formatting)

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `tidymac/__init__.py`
- Create: `tidymac/core/__init__.py`
- Create: `tidymac/tui/__init__.py`
- Create: `tidymac/tui/screens/__init__.py`
- Create: `tidymac/tui/widgets/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "tidymac"
version = "0.1.0"
description = "macOS system manager — disk analysis, cleanup, and package management"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.80",
    "pydantic>=2.0",
    "psutil>=5.9",
    "humanize>=4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
tidymac = "tidymac.cli:main"
```

**Step 2: Create all `__init__.py` files**

All empty except `tidymac/__init__.py`:

```python
"""TidyMac — macOS system manager."""

__version__ = "0.1.0"
```

**Step 3: Install in dev mode**

Run: `cd /Users/lap16400-local/Working/projects/ai-projects/agent-tools-plugin && pip install -e ".[dev]"`
Expected: Successfully installed tidymac + dependencies

**Step 4: Initialize git and commit**

```bash
git init
git add pyproject.toml tidymac/ tests/
git commit -m "chore: scaffold tidymac project"
```

---

### Task 2: Pydantic Data Models

**Files:**
- Create: `tidymac/core/models.py`
- Create: `tests/test_models.py`

**Step 1: Write failing tests for models**

```python
# tests/test_models.py
from pathlib import Path
from datetime import datetime

from tidymac.core.models import (
    FileInfo,
    DiskTree,
    DiskUsage,
    CleanTarget,
    CleanResult,
    Package,
)


def test_file_info_creation():
    f = FileInfo(path=Path("/tmp/test.txt"), size=1024, modified=datetime(2026, 1, 1))
    assert f.size == 1024
    assert f.path == Path("/tmp/test.txt")


def test_disk_tree_total_size():
    child1 = DiskTree(name="a.txt", path=Path("/tmp/a.txt"), size=100, children=[])
    child2 = DiskTree(name="b.txt", path=Path("/tmp/b.txt"), size=200, children=[])
    parent = DiskTree(name="tmp", path=Path("/tmp"), size=300, children=[child1, child2])
    assert parent.size == 300
    assert len(parent.children) == 2


def test_disk_usage_percent():
    usage = DiskUsage(total=1000, used=750, free=250, percent=75.0)
    assert usage.percent == 75.0
    assert usage.total - usage.used == usage.free


def test_clean_target_safe_flag():
    t = CleanTarget(
        path=Path("/tmp/.DS_Store"),
        category="ds_store",
        size=4096,
        safe=True,
    )
    assert t.safe is True


def test_clean_result_summary():
    r = CleanResult(cleaned=5, bytes_freed=1048576, errors=[])
    assert r.cleaned == 5
    assert r.bytes_freed == 1048576
    assert len(r.errors) == 0


def test_package_creation():
    p = Package(
        name="wget",
        version="1.21",
        size=3_000_000,
        manager="homebrew",
        is_orphan=False,
    )
    assert p.manager == "homebrew"
    assert p.is_orphan is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tidymac.core.models'`

**Step 3: Implement models**

```python
# tidymac/core/models.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class FileInfo(BaseModel):
    path: Path
    size: int  # bytes
    modified: datetime


class DiskTree(BaseModel):
    name: str
    path: Path
    size: int  # bytes (aggregate for directories)
    children: list[DiskTree] = []


class DiskUsage(BaseModel):
    total: int
    used: int
    free: int
    percent: float


class CleanTarget(BaseModel):
    path: Path
    category: str  # e.g. "ds_store", "pycache", "node_modules", "cache"
    size: int
    safe: bool  # True = auto-clean, False = needs confirmation


class CleanResult(BaseModel):
    cleaned: int  # number of targets cleaned
    bytes_freed: int
    errors: list[str] = []


class Package(BaseModel):
    name: str
    version: str
    size: int  # bytes, 0 if unknown
    manager: str  # "homebrew", "npm", "pip"
    is_orphan: bool = False
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add tidymac/core/models.py tests/test_models.py
git commit -m "feat: add pydantic data models"
```

---

### Task 3: Disk Scanner (`core/disk.py`)

**Files:**
- Create: `tidymac/core/disk.py`
- Create: `tests/test_disk.py`

**Step 1: Write failing tests**

```python
# tests/test_disk.py
import os
import tempfile
from pathlib import Path

from tidymac.core.disk import scan_directory, find_large_files, get_disk_usage


def test_scan_directory_returns_tree():
    with tempfile.TemporaryDirectory() as tmp:
        # Create test files
        Path(tmp, "file1.txt").write_text("hello")
        Path(tmp, "file2.txt").write_text("world!!")
        sub = Path(tmp, "subdir")
        sub.mkdir()
        Path(sub, "file3.txt").write_text("nested content here")

        tree = scan_directory(Path(tmp))
        assert tree.name == Path(tmp).name
        assert tree.size > 0
        assert len(tree.children) == 3  # file1, file2, subdir


def test_scan_directory_child_sizes():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "small.txt").write_text("x")
        Path(tmp, "big.txt").write_text("x" * 1000)

        tree = scan_directory(Path(tmp))
        sizes = {c.name: c.size for c in tree.children}
        assert sizes["big.txt"] > sizes["small.txt"]


def test_find_large_files():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "small.txt").write_text("x")
        Path(tmp, "big.txt").write_text("x" * 10000)
        Path(tmp, "medium.txt").write_text("x" * 500)

        large = find_large_files(Path(tmp), min_size=100)
        names = [f.path.name for f in large]
        assert "big.txt" in names
        assert "medium.txt" in names
        assert "small.txt" not in names


def test_find_large_files_sorted_desc():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "a.txt").write_text("x" * 500)
        Path(tmp, "b.txt").write_text("x" * 10000)

        large = find_large_files(Path(tmp), min_size=100)
        assert large[0].size >= large[-1].size


def test_get_disk_usage():
    usage = get_disk_usage()
    assert usage.total > 0
    assert usage.used > 0
    assert usage.free > 0
    assert 0 < usage.percent < 100
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_disk.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement disk scanner**

```python
# tidymac/core/disk.py
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import psutil

from tidymac.core.models import DiskTree, DiskUsage, FileInfo


def scan_directory(path: Path, max_depth: int = 10) -> DiskTree:
    """Recursively scan a directory and return a size-annotated tree."""
    path = path.resolve()
    children: list[DiskTree] = []
    total_size = 0

    try:
        entries = sorted(path.iterdir(), key=lambda e: e.name)
    except PermissionError:
        return DiskTree(name=path.name, path=path, size=0, children=[])

    for entry in entries:
        try:
            if entry.is_symlink():
                continue
            if entry.is_file():
                size = entry.stat().st_size
                total_size += size
                children.append(
                    DiskTree(name=entry.name, path=entry, size=size, children=[])
                )
            elif entry.is_dir() and max_depth > 0:
                subtree = scan_directory(entry, max_depth=max_depth - 1)
                total_size += subtree.size
                children.append(subtree)
        except (PermissionError, OSError):
            continue

    return DiskTree(name=path.name, path=path, size=total_size, children=children)


def find_large_files(
    path: Path, min_size: int = 100 * 1024 * 1024, limit: int = 50
) -> list[FileInfo]:
    """Find files larger than min_size bytes, sorted by size descending."""
    path = path.resolve()
    results: list[FileInfo] = []

    for root, _dirs, files in os.walk(path):
        for name in files:
            filepath = Path(root) / name
            try:
                if filepath.is_symlink():
                    continue
                stat = filepath.stat()
                if stat.st_size >= min_size:
                    results.append(
                        FileInfo(
                            path=filepath,
                            size=stat.st_size,
                            modified=datetime.fromtimestamp(stat.st_mtime),
                        )
                    )
            except (PermissionError, OSError):
                continue

    results.sort(key=lambda f: f.size, reverse=True)
    return results[:limit]


def get_disk_usage(path: str = "/") -> DiskUsage:
    """Get overall disk usage for the given mount point."""
    usage = psutil.disk_usage(path)
    return DiskUsage(
        total=usage.total,
        used=usage.used,
        free=usage.free,
        percent=usage.percent,
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_disk.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add tidymac/core/disk.py tests/test_disk.py
git commit -m "feat: add disk scanner and usage monitor"
```

---

### Task 4: Cleanup Engine (`core/cleanup.py`)

**Files:**
- Create: `tidymac/core/cleanup.py`
- Create: `tests/test_cleanup.py`

**Step 1: Write failing tests**

```python
# tests/test_cleanup.py
import tempfile
from pathlib import Path

from tidymac.core.cleanup import detect_cleanable, categorize_targets, clean


def test_detect_ds_store():
    with tempfile.TemporaryDirectory() as tmp:
        ds = Path(tmp, ".DS_Store")
        ds.write_bytes(b"\x00" * 100)

        targets = detect_cleanable(Path(tmp))
        paths = [t.path for t in targets]
        assert ds in paths


def test_detect_pycache():
    with tempfile.TemporaryDirectory() as tmp:
        pc = Path(tmp, "__pycache__")
        pc.mkdir()
        Path(pc, "mod.cpython-311.pyc").write_bytes(b"\x00" * 200)

        targets = detect_cleanable(Path(tmp))
        categories = [t.category for t in targets]
        assert "pycache" in categories


def test_detect_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        nm = Path(tmp, "project", "node_modules")
        nm.mkdir(parents=True)
        Path(nm, "pkg.js").write_text("module.exports = {}")

        targets = detect_cleanable(Path(tmp))
        nm_targets = [t for t in targets if t.category == "node_modules"]
        assert len(nm_targets) > 0
        assert nm_targets[0].safe is False  # requires confirmation


def test_categorize_targets():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, ".DS_Store").write_bytes(b"\x00" * 100)
        nm = Path(tmp, "node_modules")
        nm.mkdir()
        Path(nm, "pkg.js").write_text("x")

        targets = detect_cleanable(Path(tmp))
        categorized = categorize_targets(targets)
        assert "safe" in categorized
        assert "confirm" in categorized


def test_clean_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        ds = Path(tmp, ".DS_Store")
        ds.write_bytes(b"\x00" * 100)

        targets = detect_cleanable(Path(tmp))
        result = clean(targets, dry_run=True)
        assert result.bytes_freed > 0
        assert ds.exists()  # dry run — file still there


def test_clean_actually_deletes():
    with tempfile.TemporaryDirectory() as tmp:
        ds = Path(tmp, ".DS_Store")
        ds.write_bytes(b"\x00" * 100)

        targets = detect_cleanable(Path(tmp))
        safe_targets = [t for t in targets if t.safe]
        result = clean(safe_targets, dry_run=False)
        assert result.cleaned > 0
        assert not ds.exists()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cleanup.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement cleanup engine**

```python
# tidymac/core/cleanup.py
from __future__ import annotations

import os
import shutil
from pathlib import Path

from tidymac.core.models import CleanTarget, CleanResult

# Patterns that are safe to auto-delete
SAFE_PATTERNS: dict[str, str] = {
    ".DS_Store": "ds_store",
    "Thumbs.db": "thumbs_db",
}

SAFE_DIRS: dict[str, str] = {
    "__pycache__": "pycache",
}

# Directories that need confirmation
CONFIRM_DIRS: dict[str, str] = {
    "node_modules": "node_modules",
}

# Cache directories to detect (under ~/Library/Caches or manager-specific)
CACHE_PATHS: list[tuple[Path, str, bool]] = [
    (Path.home() / "Library/Caches/Homebrew", "brew_cache", True),
    (Path.home() / "Library/Caches/pip", "pip_cache", True),
    (Path.home() / ".npm/_cacache", "npm_cache", True),
]


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += (Path(root) / f).stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def detect_cleanable(path: Path) -> list[CleanTarget]:
    """Scan path for cleanable files and directories."""
    path = path.resolve()
    targets: list[CleanTarget] = []

    for root, dirs, files in os.walk(path):
        root_path = Path(root)

        # Check safe file patterns
        for fname in files:
            if fname in SAFE_PATTERNS:
                fpath = root_path / fname
                try:
                    size = fpath.stat().st_size
                    targets.append(
                        CleanTarget(
                            path=fpath,
                            category=SAFE_PATTERNS[fname],
                            size=size,
                            safe=True,
                        )
                    )
                except OSError:
                    continue

        # Check directories — modify dirs in-place to skip traversal into matched dirs
        skip_dirs: list[str] = []
        for dname in dirs:
            dpath = root_path / dname

            if dname in SAFE_DIRS:
                size = _dir_size(dpath)
                targets.append(
                    CleanTarget(
                        path=dpath,
                        category=SAFE_DIRS[dname],
                        size=size,
                        safe=True,
                    )
                )
                skip_dirs.append(dname)

            elif dname in CONFIRM_DIRS:
                size = _dir_size(dpath)
                targets.append(
                    CleanTarget(
                        path=dpath,
                        category=CONFIRM_DIRS[dname],
                        size=size,
                        safe=False,
                    )
                )
                skip_dirs.append(dname)

        for sd in skip_dirs:
            dirs.remove(sd)

    return targets


def detect_caches() -> list[CleanTarget]:
    """Detect system-level cache directories (brew, pip, npm)."""
    targets: list[CleanTarget] = []
    for cache_path, category, safe in CACHE_PATHS:
        if cache_path.exists():
            size = _dir_size(cache_path)
            if size > 0:
                targets.append(
                    CleanTarget(path=cache_path, category=category, size=size, safe=safe)
                )
    return targets


def categorize_targets(
    targets: list[CleanTarget],
) -> dict[str, list[CleanTarget]]:
    """Split targets into 'safe' (auto-clean) and 'confirm' (needs approval)."""
    return {
        "safe": [t for t in targets if t.safe],
        "confirm": [t for t in targets if not t.safe],
    }


def clean(targets: list[CleanTarget], dry_run: bool = False) -> CleanResult:
    """Delete the given targets. If dry_run=True, calculate but don't delete."""
    cleaned = 0
    bytes_freed = 0
    errors: list[str] = []

    for target in targets:
        try:
            bytes_freed += target.size
            if not dry_run:
                if target.path.is_dir():
                    shutil.rmtree(target.path)
                else:
                    target.path.unlink()
            cleaned += 1
        except OSError as e:
            errors.append(f"{target.path}: {e}")

    return CleanResult(cleaned=cleaned, bytes_freed=bytes_freed, errors=errors)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cleanup.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add tidymac/core/cleanup.py tests/test_cleanup.py
git commit -m "feat: add cleanup detection and execution engine"
```

---

### Task 5: Package Manager Queries (`core/packages.py`)

**Files:**
- Create: `tidymac/core/packages.py`
- Create: `tests/test_packages.py`

**Step 1: Write failing tests**

```python
# tests/test_packages.py
from unittest.mock import patch, MagicMock

from tidymac.core.packages import (
    list_homebrew,
    list_npm_global,
    list_pip,
    find_orphans,
)


BREW_LIST_OUTPUT = """\
wget\t1.21.4
git\t2.43.0
jq\t1.7.1
"""

BREW_DEPS_OUTPUT = """\
git: pcre2 gettext
jq:
wget: openssl libidn2
"""


@patch("tidymac.core.packages._run_cmd")
def test_list_homebrew(mock_run):
    mock_run.side_effect = [
        BREW_LIST_OUTPUT.strip(),  # brew list --versions
    ]
    packages = list_homebrew()
    assert len(packages) >= 3
    assert all(p.manager == "homebrew" for p in packages)
    names = [p.name for p in packages]
    assert "wget" in names


NPM_LIST_OUTPUT = """\
/usr/local/lib
├── npm@10.2.0
├── typescript@5.3.3
└── prettier@3.1.0
"""


@patch("tidymac.core.packages._run_cmd")
def test_list_npm_global(mock_run):
    mock_run.return_value = NPM_LIST_OUTPUT.strip()
    packages = list_npm_global()
    assert len(packages) == 3
    assert all(p.manager == "npm" for p in packages)
    names = [p.name for p in packages]
    assert "typescript" in names


PIP_LIST_OUTPUT = """\
[
  {"name": "requests", "version": "2.31.0"},
  {"name": "numpy", "version": "1.26.0"},
  {"name": "pip", "version": "24.0"}
]
"""


@patch("tidymac.core.packages._run_cmd")
def test_list_pip(mock_run):
    mock_run.return_value = PIP_LIST_OUTPUT.strip()
    packages = list_pip()
    assert len(packages) == 3
    assert all(p.manager == "pip" for p in packages)
    names = [p.name for p in packages]
    assert "requests" in names


@patch("tidymac.core.packages._run_cmd")
def test_find_orphans_homebrew(mock_run):
    mock_run.return_value = "jq\nwget"
    orphans = find_orphans("homebrew")
    names = [p.name for p in orphans]
    assert "jq" in names
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_packages.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement package manager queries**

```python
# tidymac/core/packages.py
from __future__ import annotations

import json
import re
import subprocess

from tidymac.core.models import Package


def _run_cmd(cmd: list[str], timeout: int = 30) -> str:
    """Run a shell command and return stdout. Returns empty string on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def list_homebrew() -> list[Package]:
    """List installed Homebrew formulae and casks."""
    output = _run_cmd(["brew", "list", "--versions"])
    if not output:
        return []

    packages: list[Package] = []
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            name = parts[0]
            version = parts[-1]
            packages.append(
                Package(name=name, version=version, size=0, manager="homebrew")
            )
    return packages


def list_npm_global() -> list[Package]:
    """List globally installed npm packages."""
    output = _run_cmd(["npm", "list", "-g", "--depth=0"])
    if not output:
        return []

    packages: list[Package] = []
    for line in output.splitlines():
        # Match lines like "├── typescript@5.3.3" or "└── prettier@3.1.0"
        match = re.search(r"[├└]──\s+(.+)@(.+)$", line)
        if match:
            name, version = match.group(1), match.group(2)
            packages.append(
                Package(name=name, version=version, size=0, manager="npm")
            )
    return packages


def list_pip() -> list[Package]:
    """List installed pip packages."""
    output = _run_cmd(["pip", "list", "--format=json"])
    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    return [
        Package(
            name=item["name"],
            version=item["version"],
            size=0,
            manager="pip",
        )
        for item in data
    ]


def find_orphans(manager: str) -> list[Package]:
    """Find packages that nothing else depends on."""
    if manager == "homebrew":
        output = _run_cmd(["brew", "autoremove", "--dry-run"])
        if not output:
            return []
        return [
            Package(name=line.strip(), version="", size=0, manager="homebrew", is_orphan=True)
            for line in output.splitlines()
            if line.strip() and not line.startswith("=")
        ]

    # npm and pip don't have great orphan detection built-in
    return []


def uninstall(package: Package) -> tuple[bool, str]:
    """Uninstall a package using its manager. Returns (success, message)."""
    cmds = {
        "homebrew": ["brew", "uninstall", package.name],
        "npm": ["npm", "uninstall", "-g", package.name],
        "pip": ["pip", "uninstall", "-y", package.name],
    }
    cmd = cmds.get(package.manager)
    if not cmd:
        return False, f"Unknown manager: {package.manager}"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, f"Uninstalled {package.name}"
        return False, result.stderr.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, str(e)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_packages.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add tidymac/core/packages.py tests/test_packages.py
git commit -m "feat: add package manager queries (brew, npm, pip)"
```

---

### Task 6: Core `__init__` Exports

**Files:**
- Modify: `tidymac/core/__init__.py`

**Step 1: Add clean public API**

```python
# tidymac/core/__init__.py
from tidymac.core.disk import scan_directory, find_large_files, get_disk_usage
from tidymac.core.cleanup import detect_cleanable, categorize_targets, clean, detect_caches
from tidymac.core.packages import list_homebrew, list_npm_global, list_pip, find_orphans, uninstall

__all__ = [
    "scan_directory", "find_large_files", "get_disk_usage",
    "detect_cleanable", "categorize_targets", "clean", "detect_caches",
    "list_homebrew", "list_npm_global", "list_pip", "find_orphans", "uninstall",
]
```

**Step 2: Verify all tests still pass**

Run: `pytest tests/ -v`
Expected: All 21 tests PASS

**Step 3: Commit**

```bash
git add tidymac/core/__init__.py
git commit -m "feat: export core public API"
```

---

### Task 7: TUI — Textual App Shell & Dashboard

**Files:**
- Create: `tidymac/tui/app.py`
- Create: `tidymac/tui/screens/dashboard.py`
- Create: `tidymac/tui/styles.tcss`

**Step 1: Create the Textual CSS theme**

```css
/* tidymac/tui/styles.tcss */

Screen {
    background: $surface;
}

#disk-bar {
    height: 3;
    margin: 1 2;
}

.usage-ok {
    color: $success;
}

.usage-warn {
    color: $warning;
}

.usage-critical {
    color: $error;
}

.section-title {
    text-style: bold;
    margin: 1 0 0 0;
    padding: 0 1;
}

DataTable {
    height: 1fr;
}

Footer {
    background: $primary-background;
}
```

**Step 2: Create Dashboard screen**

```python
# tidymac/tui/screens/dashboard.py
from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, ProgressBar, DataTable, Label

from tidymac.core import get_disk_usage, list_homebrew, list_npm_global, list_pip


class Dashboard(Static):
    """Home dashboard showing disk usage overview and package stats."""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Disk Usage", classes="section-title"),
            Horizontal(
                ProgressBar(id="disk-bar", total=100, show_eta=False),
                Label("", id="disk-label"),
            ),
            Label("", id="disk-alert"),
            Label("Top Space Hogs", classes="section-title"),
            DataTable(id="hogs-table"),
            Label("Package Stats", classes="section-title"),
            DataTable(id="pkg-table"),
        )

    def on_mount(self) -> None:
        self._refresh_data()

    def _refresh_data(self) -> None:
        # Disk usage
        usage = get_disk_usage()
        bar = self.query_one("#disk-bar", ProgressBar)
        bar.update(progress=usage.percent)

        label = self.query_one("#disk-label", Label)
        label.update(
            f"  {humanize.naturalsize(usage.used)} / {humanize.naturalsize(usage.total)}"
            f"  ({humanize.naturalsize(usage.free)} free)"
        )

        alert = self.query_one("#disk-alert", Label)
        if usage.percent > 85:
            alert.update("  WARNING: Disk usage above 85%!")
            alert.add_class("usage-critical")
        else:
            alert.update("")

        # Package stats
        pkg_table = self.query_one("#pkg-table", DataTable)
        pkg_table.clear(columns=True)
        pkg_table.add_columns("Manager", "Installed")

        brew_count = len(list_homebrew())
        npm_count = len(list_npm_global())
        pip_count = len(list_pip())

        pkg_table.add_rows([
            ("Homebrew", str(brew_count)),
            ("npm (global)", str(npm_count)),
            ("pip", str(pip_count)),
        ])
```

**Step 3: Create main Textual app**

```python
# tidymac/tui/app.py
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from tidymac.tui.screens.dashboard import Dashboard


class TidyMacApp(App):
    """TidyMac — macOS System Manager."""

    TITLE = "TidyMac"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("?", "help", "Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Dashboard", id="tab-dashboard"):
                yield Dashboard()
            with TabPane("Disk", id="tab-disk"):
                yield Static("Disk Explorer — coming next task")
            with TabPane("Packages", id="tab-packages"):
                yield Static("Package Manager — coming next task")
        yield Footer()

    def action_refresh(self) -> None:
        dashboard = self.query_one(Dashboard)
        dashboard._refresh_data()


# Need this import for the placeholder
from textual.widgets import Static  # noqa: E402
```

**Step 4: Verify app launches**

Run: `cd /Users/lap16400-local/Working/projects/ai-projects/agent-tools-plugin && python -c "from tidymac.tui.app import TidyMacApp; print('App imports OK')"`
Expected: `App imports OK`

**Step 5: Commit**

```bash
git add tidymac/tui/app.py tidymac/tui/screens/dashboard.py tidymac/tui/styles.tcss
git commit -m "feat: add TUI app shell with dashboard screen"
```

---

### Task 8: TUI — Disk Explorer Screen

**Files:**
- Create: `tidymac/tui/screens/disk.py`
- Modify: `tidymac/tui/app.py` — replace placeholder

**Step 1: Create Disk Explorer screen**

```python
# tidymac/tui/screens/disk.py
from __future__ import annotations

from pathlib import Path

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import (
    Static,
    Tree,
    DataTable,
    Button,
    Label,
    Input,
)

from tidymac.core import scan_directory, find_large_files, detect_cleanable, categorize_targets, clean
from tidymac.core.models import DiskTree


class DiskExplorer(Static):
    """Disk explorer with tree view, large files, and cleanup wizard."""

    DEFAULT_PATH = Path.home()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Input(
                    value=str(self.DEFAULT_PATH),
                    placeholder="Path to scan...",
                    id="scan-path",
                ),
                Button("Scan", id="btn-scan", variant="primary"),
                Button("Find Large Files", id="btn-large"),
                Button("Cleanup Wizard", id="btn-cleanup", variant="warning"),
            ),
            Label("Directory Tree", classes="section-title"),
            Tree("Scanning...", id="dir-tree"),
            Label("Large Files", classes="section-title"),
            DataTable(id="large-files-table"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#large-files-table", DataTable)
        table.add_columns("Path", "Size", "Modified")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        path_input = self.query_one("#scan-path", Input)
        path = Path(path_input.value)

        if event.button.id == "btn-scan":
            self._run_scan(path)
        elif event.button.id == "btn-large":
            self._show_large_files(path)
        elif event.button.id == "btn-cleanup":
            self._run_cleanup(path)

    def _run_scan(self, path: Path) -> None:
        tree_widget = self.query_one("#dir-tree", Tree)
        tree_widget.clear()
        tree_widget.root.set_label(str(path))

        disk_tree = scan_directory(path, max_depth=3)
        self._populate_tree(tree_widget.root, disk_tree)
        tree_widget.root.expand()

    def _populate_tree(self, node, disk_tree: DiskTree) -> None:
        # Sort children by size descending
        sorted_children = sorted(disk_tree.children, key=lambda c: c.size, reverse=True)
        for child in sorted_children[:50]:  # Limit display
            size_str = humanize.naturalsize(child.size)
            label = f"{child.name}  [{size_str}]"
            if child.children:
                branch = node.add(label, expand=False)
                self._populate_tree(branch, child)
            else:
                node.add_leaf(label)

    def _show_large_files(self, path: Path) -> None:
        table = self.query_one("#large-files-table", DataTable)
        table.clear()

        # Use 1MB threshold for personal use
        files = find_large_files(path, min_size=1024 * 1024, limit=20)
        for f in files:
            table.add_row(
                str(f.path),
                humanize.naturalsize(f.size),
                f.modified.strftime("%Y-%m-%d %H:%M"),
            )

    def _run_cleanup(self, path: Path) -> None:
        targets = detect_cleanable(path)
        categorized = categorize_targets(targets)

        safe = categorized["safe"]
        if safe:
            result = clean(safe, dry_run=False)
            self.notify(
                f"Cleaned {result.cleaned} items, freed {humanize.naturalsize(result.bytes_freed)}",
                title="Auto-cleanup done",
            )

        confirm = categorized["confirm"]
        if confirm:
            total = sum(t.size for t in confirm)
            self.notify(
                f"{len(confirm)} items need confirmation ({humanize.naturalsize(total)}). "
                f"Review in Cleanup tab.",
                title="Items need review",
                severity="warning",
            )
        elif not safe:
            self.notify("Nothing to clean!", title="All clear")
```

**Step 2: Update app.py to use DiskExplorer**

Replace the Disk tab placeholder in `tidymac/tui/app.py`:

In the imports, add:
```python
from tidymac.tui.screens.disk import DiskExplorer
```

Replace:
```python
            with TabPane("Disk", id="tab-disk"):
                yield Static("Disk Explorer — coming next task")
```
With:
```python
            with TabPane("Disk", id="tab-disk"):
                yield DiskExplorer()
```

Remove the `from textual.widgets import Static  # noqa: E402` at the bottom, and add `Static` to the existing import from `textual.widgets` at the top if not already there.

**Step 3: Verify import works**

Run: `python -c "from tidymac.tui.screens.disk import DiskExplorer; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add tidymac/tui/screens/disk.py tidymac/tui/app.py
git commit -m "feat: add disk explorer screen with tree view and cleanup"
```

---

### Task 9: TUI — Package Manager Screen

**Files:**
- Create: `tidymac/tui/screens/packages.py`
- Modify: `tidymac/tui/app.py` — replace placeholder

**Step 1: Create Package Manager screen**

```python
# tidymac/tui/screens/packages.py
from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, DataTable, Button, Label, TabbedContent, TabPane

from tidymac.core import list_homebrew, list_npm_global, list_pip, find_orphans
from tidymac.core.packages import uninstall
from tidymac.core.models import Package


class PackageManager(Static):
    """Package manager view with tabs for brew, npm, pip."""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Button("Refresh All", id="btn-pkg-refresh", variant="primary"),
            TabbedContent(
                TabPane("Homebrew", DataTable(id="brew-table")),
                TabPane("npm global", DataTable(id="npm-table")),
                TabPane("pip", DataTable(id="pip-table")),
                id="pkg-tabs",
            ),
            Label("", id="pkg-status"),
        )

    def on_mount(self) -> None:
        for table_id in ("brew-table", "npm-table", "pip-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Name", "Version", "Orphan?")
            table.cursor_type = "row"

        self._load_all()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pkg-refresh":
            self._load_all()

    def _load_all(self) -> None:
        self._load_table("brew-table", list_homebrew, "homebrew")
        self._load_table("npm-table", list_npm_global, "npm")
        self._load_table("pip-table", list_pip, "pip")

    def _load_table(self, table_id: str, list_fn, manager: str) -> None:
        table = self.query_one(f"#{table_id}", DataTable)
        table.clear()

        packages = list_fn()
        orphans = {p.name for p in find_orphans(manager)}

        for pkg in sorted(packages, key=lambda p: p.name):
            is_orphan = pkg.name in orphans or pkg.is_orphan
            table.add_row(
                pkg.name,
                pkg.version,
                "Yes" if is_orphan else "",
            )

        status = self.query_one("#pkg-status", Label)
        status.update(f"Loaded {len(packages)} {manager} packages")
```

**Step 2: Update app.py to use PackageManager**

Add import:
```python
from tidymac.tui.screens.packages import PackageManager
```

Replace:
```python
            with TabPane("Packages", id="tab-packages"):
                yield Static("Package Manager — coming next task")
```
With:
```python
            with TabPane("Packages", id="tab-packages"):
                yield PackageManager()
```

**Step 3: Verify import works**

Run: `python -c "from tidymac.tui.screens.packages import PackageManager; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add tidymac/tui/screens/packages.py tidymac/tui/app.py
git commit -m "feat: add package manager screen with brew/npm/pip tabs"
```

---

### Task 10: CLI Entry Point

**Files:**
- Create: `tidymac/cli.py`

**Step 1: Implement CLI**

```python
# tidymac/cli.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import humanize

from tidymac.core import (
    scan_directory,
    find_large_files,
    get_disk_usage,
    detect_cleanable,
    categorize_targets,
    clean,
    list_homebrew,
    list_npm_global,
    list_pip,
)


def cmd_tui() -> None:
    """Launch the TUI."""
    from tidymac.tui.app import TidyMacApp

    app = TidyMacApp()
    app.run()


def cmd_scan(path: str) -> None:
    """Quick scan a directory."""
    usage = get_disk_usage()
    print(f"Disk: {humanize.naturalsize(usage.used)} / {humanize.naturalsize(usage.total)} ({usage.percent:.1f}%)")
    print()

    tree = scan_directory(Path(path), max_depth=2)
    _print_tree(tree, indent=0)


def _print_tree(tree, indent: int) -> None:
    prefix = "  " * indent
    size = humanize.naturalsize(tree.size)
    print(f"{prefix}{tree.name}  [{size}]")
    sorted_children = sorted(tree.children, key=lambda c: c.size, reverse=True)
    for child in sorted_children[:15]:
        _print_tree(child, indent + 1)


def cmd_cleanup() -> None:
    """Run cleanup wizard."""
    home = Path.home()
    print(f"Scanning {home}...")
    targets = detect_cleanable(home)
    categorized = categorize_targets(targets)

    safe = categorized["safe"]
    confirm = categorized["confirm"]

    if safe:
        total = sum(t.size for t in safe)
        print(f"\nAuto-cleaning {len(safe)} safe items ({humanize.naturalsize(total)})...")
        result = clean(safe, dry_run=False)
        print(f"  Freed {humanize.naturalsize(result.bytes_freed)}")

    if confirm:
        print(f"\n{len(confirm)} items need review:")
        for t in confirm:
            print(f"  [{t.category}] {t.path} ({humanize.naturalsize(t.size)})")
        answer = input("\nDelete these? [y/N] ").strip().lower()
        if answer == "y":
            result = clean(confirm, dry_run=False)
            print(f"  Freed {humanize.naturalsize(result.bytes_freed)}")
        else:
            print("  Skipped.")

    if not safe and not confirm:
        print("Nothing to clean!")


def cmd_packages() -> None:
    """List all packages."""
    for label, fn in [("Homebrew", list_homebrew), ("npm global", list_npm_global), ("pip", list_pip)]:
        pkgs = fn()
        print(f"\n{label} ({len(pkgs)}):")
        for p in sorted(pkgs, key=lambda x: x.name):
            print(f"  {p.name} {p.version}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TidyMac — macOS system manager")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan a directory")
    scan_p.add_argument("path", nargs="?", default=".", help="Path to scan")

    sub.add_parser("cleanup", help="Run cleanup wizard")
    sub.add_parser("packages", help="List installed packages")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args.path)
    elif args.command == "cleanup":
        cmd_cleanup()
    elif args.command == "packages":
        cmd_packages()
    else:
        cmd_tui()


if __name__ == "__main__":
    main()
```

**Step 2: Verify CLI works**

Run: `python -m tidymac.cli --help`
Expected: Shows help text with scan, cleanup, packages subcommands

**Step 3: Commit**

```bash
git add tidymac/cli.py
git commit -m "feat: add CLI entry point with scan, cleanup, packages commands"
```

---

### Task 11: Integration Smoke Test

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 2: Test CLI scan**

Run: `tidymac scan /tmp`
Expected: Prints tree with sizes

**Step 3: Test CLI packages**

Run: `tidymac packages`
Expected: Lists brew/npm/pip packages

**Step 4: Test TUI launches**

Run: `python -c "from tidymac.tui.app import TidyMacApp; print('TUI ready')"`
Expected: `TUI ready`

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: integration verification complete"
```

---

## Task Dependency Order

```
Task 1 (scaffold) → Task 2 (models) → Task 3 (disk) ─┐
                                        Task 4 (cleanup) ─┤→ Task 6 (exports) → Task 7 (dashboard) → Task 8 (disk screen) → Task 9 (pkg screen) → Task 10 (CLI) → Task 11 (smoke test)
                                        Task 5 (packages) ─┘
```

Tasks 3, 4, 5 can run in parallel after Task 2.
Tasks 7, 8, 9 are sequential (each builds on the app shell).
