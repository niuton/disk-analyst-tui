from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import DataTable, Button, Label, ContentSwitcher
from textual import work

from disk_analyst_tool.core import list_homebrew, list_npm_global, list_pip, find_orphans


class PackageManager(Widget):
    """Package manager with compact nav and size info."""

    def compose(self) -> ComposeResult:
        with Vertical():
            # Navigation bar
            with Horizontal(id="pkg-nav"):
                yield Button("Homebrew", id="btn-brew", classes="nav-btn -active")
                yield Button("npm", id="btn-npm", classes="nav-btn")
                yield Button("pip", id="btn-pip", classes="nav-btn")
                yield Button("Refresh", id="btn-pkg-refresh", classes="nav-btn-refresh")

            # Total size indicator
            yield Label("  Loading...", id="pkg-total-size")

            # Content area
            with Vertical(id="pkg-content-panel", classes="panel"):
                with ContentSwitcher(initial="brew-view"):
                    with Vertical(id="brew-view"):
                        yield DataTable(id="brew-table")
                    with Vertical(id="npm-view"):
                        yield DataTable(id="npm-table")
                    with Vertical(id="pip-view"):
                        yield DataTable(id="pip-table")

            # Status bar
            yield Label("", id="pkg-status-bar")

    def on_mount(self) -> None:
        for table_id in ("brew-table", "npm-table", "pip-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Name", "Version", "Size", "Orphan?")
            table.cursor_type = "row"

        self._load_all()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        switcher = self.query_one(ContentSwitcher)

        # Handle nav buttons
        nav_map = {
            "btn-brew": "brew-view",
            "btn-npm": "npm-view",
            "btn-pip": "pip-view",
        }

        if event.button.id in nav_map:
            switcher.current = nav_map[event.button.id]
            # Update active state
            for btn in self.query(".nav-btn"):
                btn.remove_class("-active")
            event.button.add_class("-active")
        elif event.button.id == "btn-pkg-refresh":
            self._load_all()

    def _load_all(self) -> None:
        self.query_one("#pkg-total-size", Label).update("  Loading packages...")
        self._load_brew()
        self._load_npm()
        self._load_pip()

    @work(thread=True)
    def _load_brew(self) -> None:
        packages = list_homebrew()
        orphans = {p.name for p in find_orphans("homebrew")}
        total_size = sum(p.size for p in packages)
        rows = [
            (
                pkg.name,
                pkg.version,
                humanize.naturalsize(pkg.size) if pkg.size else "-",
                "Yes" if pkg.name in orphans or pkg.is_orphan else "",
            )
            for pkg in sorted(packages, key=lambda p: p.size, reverse=True)
        ]
        self.app.call_from_thread(
            self._fill_table, "brew-table", rows,
            f"Homebrew: {len(packages)} packages, {humanize.naturalsize(total_size)}",
            total_size,
        )

    @work(thread=True)
    def _load_npm(self) -> None:
        packages = list_npm_global()
        total_size = sum(p.size for p in packages)
        rows = [
            (
                pkg.name,
                pkg.version,
                humanize.naturalsize(pkg.size) if pkg.size else "-",
                "",
            )
            for pkg in sorted(packages, key=lambda p: p.size, reverse=True)
        ]
        self.app.call_from_thread(
            self._fill_table, "npm-table", rows,
            f"npm: {len(packages)} packages, {humanize.naturalsize(total_size)}",
            total_size,
        )

    @work(thread=True)
    def _load_pip(self) -> None:
        packages = list_pip()
        total_size = sum(p.size for p in packages)
        rows = [
            (
                pkg.name,
                pkg.version,
                humanize.naturalsize(pkg.size) if pkg.size else "-",
                "",
            )
            for pkg in sorted(packages, key=lambda p: p.size, reverse=True)
        ]
        self.app.call_from_thread(
            self._fill_table, "pip-table", rows,
            f"pip: {len(packages)} packages, {humanize.naturalsize(total_size)}",
            total_size,
        )

    _totals: dict[str, int] = {}

    def _fill_table(self, table_id: str, rows: list, status: str, total_size: int) -> None:
        table = self.query_one(f"#{table_id}", DataTable)
        table.clear()
        for row in rows:
            table.add_row(*row)

        # Track totals
        self._totals[table_id] = total_size
        grand_total = sum(self._totals.values())

        self.query_one("#pkg-total-size", Label).update(
            f"  Total installed: {humanize.naturalsize(grand_total)}"
        )
        self.query_one("#pkg-status-bar", Label).update(f"  {status}")
