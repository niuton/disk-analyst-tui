from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane, DataTable

from disk_analyst_tool.tui.screens.dashboard import Dashboard
from disk_analyst_tool.tui.screens.disk import DiskExplorer
from disk_analyst_tool.tui.screens.packages import PackageManager
from disk_analyst_tool.tui.screens.docker import DockerManager


class DiskAnalystApp(App):
    """Disk Analyst — macOS System Manager."""

    TITLE = "Disk Analyst"
    SUB_TITLE = "System Manager"
    CSS_PATH = "styles.tcss"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "tab_dashboard", "Dashboard", show=True),
        Binding("2", "tab_disk", "Disk", show=True),
        Binding("3", "tab_packages", "Packages", show=True),
        Binding("4", "tab_docker", "Docker", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Dashboard", id="tab-dashboard"):
                yield Dashboard()
            with TabPane("Disk", id="tab-disk"):
                yield DiskExplorer()
            with TabPane("Packages", id="tab-packages"):
                yield PackageManager()
            with TabPane("Docker", id="tab-docker"):
                yield DockerManager()
        yield Footer()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Focus the first focusable widget in the active tab."""
        self.set_timer(0.1, lambda: self._focus_active_tab())

    def _focus_active_tab(self) -> None:
        """Find and focus the first DataTable or focusable widget in the active pane."""
        tc = self.query_one(TabbedContent)
        active_pane = tc.active_pane
        if active_pane is None:
            return

        # Try to focus the first DataTable in the active pane
        tables = active_pane.query(DataTable)
        for table in tables:
            if table.display:
                table.focus()
                return

        # Fallback: focus the pane's first focusable child
        for child in active_pane.query("*"):
            if child.can_focus:
                child.focus()
                return

    def action_refresh(self) -> None:
        dashboard = self.query_one(Dashboard)
        dashboard._refresh_data(force=True)

    def action_tab_dashboard(self) -> None:
        self.query_one(TabbedContent).active = "tab-dashboard"

    def action_tab_disk(self) -> None:
        self.query_one(TabbedContent).active = "tab-disk"

    def action_tab_packages(self) -> None:
        self.query_one(TabbedContent).active = "tab-packages"

    def action_tab_docker(self) -> None:
        self.query_one(TabbedContent).active = "tab-docker"
