from __future__ import annotations

import os
import shutil
from pathlib import Path

from disk_analyst_tool.core.models import CleanTarget, CleanResult

SAFE_PATTERNS: dict[str, str] = {
    ".DS_Store": "ds_store",
    "Thumbs.db": "thumbs_db",
}

SAFE_DIRS: dict[str, str] = {
    "__pycache__": "pycache",
}

CONFIRM_DIRS: dict[str, str] = {
    "node_modules": "node_modules",
}

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
