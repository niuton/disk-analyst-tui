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
    LoadingIndicator,
)
from textual.binding import Binding
from textual import work

from disk_analyst_tool.core import scan_directory, find_large_files, detect_cleanable, categorize_targets, clean
from disk_analyst_tool.core.models import DiskTree


class DiskExplorer(Widget):
    """Disk explorer with tree view, large files, and cleanup."""

    DEFAULT_PATH = Path.home()

    BINDINGS = [
        Binding("f5", "scan", "Scan", show=True),
        Binding("f6", "large_files", "Large Files", show=True),
        Binding("f7", "cleanup", "Cleanup", show=True),
        Binding("f8", "edit_path", "Edit Path", show=True),
        Binding("escape", "back", "Back", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            # Toolbar
            with Horizontal(id="disk-toolbar"):
                yield Input(
                    value=str(self.DEFAULT_PATH),
                    placeholder="Path to scan...",
                    id="scan-path",
                )
                yield Button("[F5] Scan", id="btn-scan", variant="primary", classes="toolbar-btn")
                yield Button("[F6] Large", id="btn-large", classes="toolbar-btn")
                yield Button("[F7] Clean", id="btn-cleanup", variant="warning", classes="toolbar-btn")

            # Loading
            yield LoadingIndicator(id="disk-loading")

            # Directory tree panel
            with Vertical(id="disk-tree-panel", classes="panel"):
                yield Label(" Directory Tree", classes="panel-title")
                yield Tree("Press F5 to scan", id="dir-tree")

            # Large files panel
            with Vertical(id="disk-files-panel", classes="panel"):
                yield Label(" Large Files", classes="panel-title")
                yield DataTable(id="large-files-table")

            # Status
            yield Label("  [F5] Scan  [F6] Large Files  [F7] Cleanup  [F8] Edit Path", id="disk-status-bar")

    def on_mount(self) -> None:
        self.query_one("#disk-loading").display = False
        table = self.query_one("#large-files-table", DataTable)
        table.add_columns("Path", "Size", "Modified")

    def _get_path(self) -> Path:
        return Path(self.query_one("#scan-path", Input).value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-scan":
            self.action_scan()
        elif event.button.id == "btn-large":
            self.action_large_files()
        elif event.button.id == "btn-cleanup":
            self.action_cleanup()

    def action_scan(self) -> None:
        self._show_loading("Scanning...")
        self._run_scan(self._get_path())

    def action_large_files(self) -> None:
        self._show_loading("Finding large files...")
        self._find_large(self._get_path())

    def action_cleanup(self) -> None:
        self._show_loading("Running cleanup...")
        self._run_cleanup(self._get_path())

    def action_edit_path(self) -> None:
        self.query_one("#scan-path", Input).focus()

    def action_back(self) -> None:
        from textual.widgets import TabbedContent
        self.app.query_one(TabbedContent).active = "tab-dashboard"

    def _show_loading(self, msg: str = "Loading...") -> None:
        self.query_one("#disk-loading").display = True
        self.query_one("#disk-status-bar", Label).update(f"  {msg}")

    def _hide_loading(self) -> None:
        self.query_one("#disk-loading").display = False

    @work(thread=True)
    def _run_scan(self, path: Path) -> None:
        disk_tree = scan_directory(path, max_depth=3)
        self.app.call_from_thread(self._render_tree, path, disk_tree)

    def _render_tree(self, path: Path, disk_tree: DiskTree) -> None:
        self._hide_loading()
        tree_widget = self.query_one("#dir-tree", Tree)
        tree_widget.clear()
        total = humanize.naturalsize(disk_tree.size)
        tree_widget.root.set_label(f"{path}  [{total}]")
        self._populate_tree(tree_widget.root, disk_tree)
        tree_widget.root.expand()
        tree_widget.focus()

        child_count = len(disk_tree.children)
        self.query_one("#disk-status-bar", Label).update(
            f"  Scanned: {child_count} items, {total}  |  [F5] Scan  [F6] Large  [F7] Clean"
        )

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
        total = sum(f.size for f in files)
        self.app.call_from_thread(self._render_large_files, rows, len(files), total)

    def _render_large_files(self, rows: list, count: int, total: int) -> None:
        self._hide_loading()
        table = self.query_one("#large-files-table", DataTable)
        table.clear()
        for row in rows:
            table.add_row(*row)
        table.focus()

        self.query_one("#disk-status-bar", Label).update(
            f"  Found {count} large files ({humanize.naturalsize(total)})  |  [F5] Scan  [F6] Large  [F7] Clean"
        )

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

        self.app.call_from_thread(self._cleanup_done, msg)

    def _cleanup_done(self, msg: str) -> None:
        self._hide_loading()
        self.notify(msg, title="Cleanup")
        self.query_one("#disk-status-bar", Label).update(
            f"  {msg}  |  [F5] Scan  [F6] Large  [F7] Clean"
        )
