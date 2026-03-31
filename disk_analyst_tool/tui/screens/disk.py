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
from textual.screen import ModalScreen
from textual import work

from disk_analyst_tool.core import scan_directory, find_large_files, detect_cleanable, categorize_targets, clean
from disk_analyst_tool.core.models import DiskTree, CleanTarget


class CleanupReview(ModalScreen[list[int]]):
    """Modal showing items that need confirmation before cleanup."""

    CSS = """
    CleanupReview {
        align: center middle;
    }
    #cleanup-dialog {
        width: 90%;
        max-width: 100;
        height: 80%;
        border: round $warning;
        background: $surface;
        padding: 1 2;
    }
    #cleanup-dialog Label {
        width: 100%;
    }
    #cleanup-header {
        height: 2;
        text-style: bold;
        color: $warning;
    }
    #cleanup-review-table {
        height: 1fr;
    }
    #cleanup-actions {
        layout: horizontal;
        height: auto;
        align: center middle;
        margin: 1 0 0 0;
    }
    #cleanup-actions Button {
        margin: 0 1;
    }
    """

    def __init__(self, targets: list[CleanTarget], auto_cleaned: int, auto_freed: int) -> None:
        super().__init__()
        self._targets = targets
        self._auto_cleaned = auto_cleaned
        self._auto_freed = auto_freed
        self._selected: set[int] = set()

    def compose(self) -> ComposeResult:
        with Vertical(id="cleanup-dialog"):
            if self._auto_cleaned > 0:
                yield Label(
                    f"  Auto-cleaned {self._auto_cleaned} safe items, "
                    f"freed {humanize.naturalsize(self._auto_freed)}\n"
                    f"  {len(self._targets)} items need your review:",
                    id="cleanup-header",
                )
            else:
                yield Label(
                    f"  {len(self._targets)} items need your review:",
                    id="cleanup-header",
                )
            yield DataTable(id="cleanup-review-table")
            with Horizontal(id="cleanup-actions"):
                yield Button("Delete Selected", id="btn-cleanup-delete", variant="error")
                yield Button("Select All", id="btn-cleanup-all", variant="warning")
                yield Button("Cancel", id="btn-cleanup-cancel")

    def on_mount(self) -> None:
        table = self.query_one("#cleanup-review-table", DataTable)
        table.add_columns("Sel", "Category", "Path", "Size")
        table.cursor_type = "row"

        for i, target in enumerate(self._targets):
            table.add_row(
                "[ ]",
                target.category,
                str(target.path),
                humanize.naturalsize(target.size),
                key=str(i),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Toggle selection on row click/enter."""
        idx = int(event.row_key.value)
        table = self.query_one("#cleanup-review-table", DataTable)

        if idx in self._selected:
            self._selected.discard(idx)
            table.update_cell_at((event.cursor_row, 0), "[ ]")
        else:
            self._selected.add(idx)
            table.update_cell_at((event.cursor_row, 0), "[x]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cleanup-delete":
            self.dismiss(list(self._selected))
        elif event.button.id == "btn-cleanup-all":
            table = self.query_one("#cleanup-review-table", DataTable)
            self._selected = set(range(len(self._targets)))
            for i in range(len(self._targets)):
                table.update_cell_at((i, 0), "[x]")
        elif event.button.id == "btn-cleanup-cancel":
            self.dismiss([])


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
        self._show_loading("Analyzing cleanup targets...")
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
        auto_cleaned = 0
        auto_freed = 0
        if safe:
            result = clean(safe, dry_run=False)
            auto_cleaned = result.cleaned
            auto_freed = result.bytes_freed

        confirm = categorized["confirm"]
        self.app.call_from_thread(self._show_cleanup_review, confirm, auto_cleaned, auto_freed)

    def _show_cleanup_review(self, confirm: list[CleanTarget], auto_cleaned: int, auto_freed: int) -> None:
        self._hide_loading()

        if not confirm and auto_cleaned == 0:
            self.notify("Nothing to clean!", title="All clear")
            self.query_one("#disk-status-bar", Label).update(
                "  Nothing to clean!  |  [F5] Scan  [F6] Large  [F7] Clean"
            )
            return

        if not confirm:
            msg = f"Cleaned {auto_cleaned} items, freed {humanize.naturalsize(auto_freed)}"
            self.notify(msg, title="Cleanup done")
            self.query_one("#disk-status-bar", Label).update(
                f"  {msg}  |  [F5] Scan  [F6] Large  [F7] Clean"
            )
            return

        # Show review modal for items needing confirmation
        self.app.push_screen(
            CleanupReview(confirm, auto_cleaned, auto_freed),
            callback=self._on_cleanup_review_done,
        )
        # Store targets for callback
        self._pending_confirm = confirm

    def _on_cleanup_review_done(self, selected_indices: list[int]) -> None:
        if not selected_indices:
            self.query_one("#disk-status-bar", Label).update(
                "  Cleanup cancelled  |  [F5] Scan  [F6] Large  [F7] Clean"
            )
            return

        targets_to_clean = [self._pending_confirm[i] for i in selected_indices]
        self._do_confirmed_cleanup(targets_to_clean)

    @work(thread=True)
    def _do_confirmed_cleanup(self, targets: list[CleanTarget]) -> None:
        result = clean(targets, dry_run=False)
        msg = f"Cleaned {result.cleaned} items, freed {humanize.naturalsize(result.bytes_freed)}"
        if result.errors:
            msg += f" ({len(result.errors)} errors)"
        self.app.call_from_thread(self._cleanup_final, msg)

    def _cleanup_final(self, msg: str) -> None:
        self.notify(msg, title="Cleanup complete")
        self.query_one("#disk-status-bar", Label).update(
            f"  {msg}  |  [F5] Scan  [F6] Large  [F7] Clean"
        )
