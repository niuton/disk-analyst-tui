import tempfile
from pathlib import Path

from disk_analyst_tool.core.cleanup import detect_cleanable, categorize_targets, clean


def test_detect_ds_store():
    with tempfile.TemporaryDirectory() as tmp:
        ds = Path(tmp, ".DS_Store").resolve()
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
        assert nm_targets[0].safe is False


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
        assert ds.exists()


def test_clean_actually_deletes():
    with tempfile.TemporaryDirectory() as tmp:
        ds = Path(tmp, ".DS_Store")
        ds.write_bytes(b"\x00" * 100)

        targets = detect_cleanable(Path(tmp))
        safe_targets = [t for t in targets if t.safe]
        result = clean(safe_targets, dry_run=False)
        assert result.cleaned > 0
        assert not ds.exists()
