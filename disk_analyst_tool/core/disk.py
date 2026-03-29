from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import psutil

from disk_analyst_tool.core.models import DiskTree, DiskUsage, FileInfo


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
