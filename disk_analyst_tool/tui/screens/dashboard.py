from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import ProgressBar, DataTable, Label, LoadingIndicator
from textual import work

from disk_analyst_tool.core import get_disk_usage, list_homebrew, list_npm_global, list_pip


class Dashboard(Widget):
    """Home dashboard with disk usage and package overview."""

    def compose(self) -> ComposeResult:
        with Vertical():
            # Disk usage panel
            with Vertical(id="dash-disk-panel", classes="panel"):
                yield Label(" Disk Usage", classes="panel-title")
                yield ProgressBar(id="disk-bar", total=100, show_eta=False)
                yield Label("", id="disk-label")
                yield Label("", id="disk-detail")
                yield Label("", id="disk-alert")

            # Package stats panel
            with Vertical(id="dash-pkg-panel", classes="panel"):
                yield Label(" Package Overview", classes="panel-title")
                yield LoadingIndicator(id="dash-loading")
                yield DataTable(id="pkg-table")

    def on_mount(self) -> None:
        self.query_one("#pkg-table").display = False
        self._refresh_data()

    def _refresh_data(self) -> None:
        usage = get_disk_usage()

        bar = self.query_one("#disk-bar", ProgressBar)
        bar.update(progress=usage.percent)

        label = self.query_one("#disk-label", Label)
        label.update(
            f"  Used: {humanize.naturalsize(usage.used)}  /  "
            f"Total: {humanize.naturalsize(usage.total)}  "
            f"({usage.percent:.1f}%)"
        )

        detail = self.query_one("#disk-detail", Label)
        detail.update(f"  Free: {humanize.naturalsize(usage.free)}")

        alert = self.query_one("#disk-alert", Label)
        if usage.percent > 85:
            alert.update("  !! Disk usage above 85% — consider running cleanup")
        elif usage.percent > 70:
            alert.update("  ! Disk usage above 70%")
        else:
            alert.update("")

        # Show loading, load packages
        self.query_one("#dash-loading").display = True
        self.query_one("#pkg-table").display = False
        self._load_pkg_counts()

    @work(thread=True)
    def _load_pkg_counts(self) -> None:
        brew = list_homebrew()
        npm = list_npm_global()
        pip_pkgs = list_pip()

        brew_size = sum(p.size for p in brew)
        npm_size = sum(p.size for p in npm)
        pip_size = sum(p.size for p in pip_pkgs)

        self.app.call_from_thread(
            self._update_pkg_table,
            len(brew), brew_size,
            len(npm), npm_size,
            len(pip_pkgs), pip_size,
        )

    def _update_pkg_table(
        self,
        brew_n: int, brew_s: int,
        npm_n: int, npm_s: int,
        pip_n: int, pip_s: int,
    ) -> None:
        # Hide loading, show table
        self.query_one("#dash-loading").display = False
        self.query_one("#pkg-table").display = True

        pkg_table = self.query_one("#pkg-table", DataTable)
        pkg_table.clear(columns=True)
        pkg_table.add_columns("Manager", "Packages", "Total Size")

        total = brew_s + npm_s + pip_s
        pkg_table.add_rows([
            ("Homebrew", str(brew_n), humanize.naturalsize(brew_s)),
            ("npm (global)", str(npm_n), humanize.naturalsize(npm_s)),
            ("pip", str(pip_n), humanize.naturalsize(pip_s)),
            ("TOTAL", str(brew_n + npm_n + pip_n), humanize.naturalsize(total)),
        ])
