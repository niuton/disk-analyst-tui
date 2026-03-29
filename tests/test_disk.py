import tempfile
from pathlib import Path

from disk_analyst_tool.core.disk import scan_directory, find_large_files, get_disk_usage


def test_scan_directory_returns_tree():
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "file1.txt").write_text("hello")
        Path(tmp, "file2.txt").write_text("world!!")
        sub = Path(tmp, "subdir")
        sub.mkdir()
        Path(sub, "file3.txt").write_text("nested content here")

        tree = scan_directory(Path(tmp))
        assert tree.name == Path(tmp).name
        assert tree.size > 0
        assert len(tree.children) == 3


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
