from __future__ import annotations

from pathlib import Path

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import (
    Tree,
    DataTable,
    Button,
    Label,
    Input,
)
from textual import work

from disk_analyst_tool.core import scan_directory, find_large_files, detect_cleanable, categorize_targets, clean
from disk_analyst_tool.core.models import DiskTree


class DiskExplorer(Widget):
    """Disk explorer with tree view, large files, and cleanup."""

    DEFAULT_PATH = Path.home()

    def compose(self) -> ComposeResult:
        with Vertical():
            # Toolbar
            with Horizontal(id="disk-toolbar"):
                yield Input(
                    value=str(self.DEFAULT_PATH),
                    placeholder="Path to scan...",
                    id="scan-path",
                )
                yield Button("Scan", id="btn-scan", variant="primary", classes="toolbar-btn")
                yield Button("Large Files", id="btn-large", classes="toolbar-btn")
                yield Button("Cleanup", id="btn-cleanup", variant="warning", classes="toolbar-btn")

            # Directory tree panel
            with Vertical(id="disk-tree-panel", classes="panel"):
                yield Label(" Directory Tree", classes="panel-title")
                yield Tree("Press [Scan] to start", id="dir-tree")

            # Large files panel
            with Vertical(id="disk-files-panel", classes="panel"):
                yield Label(" Large Files", classes="panel-title")
                yield DataTable(id="large-files-table")

    def on_mount(self) -> None:
        table = self.query_one("#large-files-table", DataTable)
        table.add_columns("Path", "Size", "Modified")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        path_input = self.query_one("#scan-path", Input)
        path = Path(path_input.value)

        if event.button.id == "btn-scan":
            self._run_scan(path)
        elif event.button.id == "btn-large":
            self._find_large(path)
        elif event.button.id == "btn-cleanup":
            self._run_cleanup(path)

    @work(thread=True)
    def _run_scan(self, path: Path) -> None:
        disk_tree = scan_directory(path, max_depth=3)
        self.app.call_from_thread(self._render_tree, path, disk_tree)

    def _render_tree(self, path: Path, disk_tree: DiskTree) -> None:
        tree_widget = self.query_one("#dir-tree", Tree)
        tree_widget.clear()
        total = humanize.naturalsize(disk_tree.size)
        tree_widget.root.set_label(f"{path}  [{total}]")
        self._populate_tree(tree_widget.root, disk_tree)
        tree_widget.root.expand()

    def _populate_tree(self, node, disk_tree: DiskTree) -> None:
        sorted_children = sorted(disk_tree.children, key=lambda c: c.size, reverse=True)
        for child in sorted_children[:50]:
            size_str = humanize.naturalsize(child.size)
            label = f"{child.name}  [{size_str}]"
            if child.children:
                branch = node.add(label, expand=False)
                self._populate_tree(branch, child)
            else:
                node.add_leaf(label)

    @work(thread=True)
    def _find_large(self, path: Path) -> None:
        files = find_large_files(path, min_size=1024 * 1024, limit=20)
        rows = [
            (str(f.path), humanize.naturalsize(f.size), f.modified.strftime("%Y-%m-%d %H:%M"))
            for f in files
        ]
        self.app.call_from_thread(self._render_large_files, rows)

    def _render_large_files(self, rows: list) -> None:
        table = self.query_one("#large-files-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(*row)

    @work(thread=True)
    def _run_cleanup(self, path: Path) -> None:
        targets = detect_cleanable(path)
        categorized = categorize_targets(targets)

        safe = categorized["safe"]
        msg = ""
        if safe:
            result = clean(safe, dry_run=False)
            msg = f"Cleaned {result.cleaned} items, freed {humanize.naturalsize(result.bytes_freed)}"

        confirm = categorized["confirm"]
        if confirm:
            total = sum(t.size for t in confirm)
            msg += f" | {len(confirm)} items need manual review ({humanize.naturalsize(total)})"

        if not safe and not confirm:
            msg = "Nothing to clean!"

        self.app.call_from_thread(self.notify, msg, title="Cleanup")
