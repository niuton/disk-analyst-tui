from pathlib import Path
from datetime import datetime

from disk_analyst_tool.core.models import (
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
