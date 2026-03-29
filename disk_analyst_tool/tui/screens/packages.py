from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import DataTable, Button, Label, ContentSwitcher, Input, LoadingIndicator
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import work, on

from disk_analyst_tool.core import list_homebrew, list_npm_global, list_pip, find_orphans
from disk_analyst_tool.core.packages import uninstall
from disk_analyst_tool.core.models import Package


class ConfirmUninstall(ModalScreen[bool]):
    """Confirmation dialog for uninstalling a package."""

    CSS = """
    ConfirmUninstall {
        align: center middle;
    }
    #confirm-dialog {
        width: 60;
        height: auto;
        max-height: 12;
        border: round $error;
        background: $surface;
        padding: 1 2;
    }
    #confirm-dialog Label {
        width: 100%;
        margin: 0 0 1 0;
    }
    #confirm-buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }
    #confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, pkg_name: str, pkg_manager: str, pkg_size: str) -> None:
        super().__init__()
        self.pkg_name = pkg_name
        self.pkg_manager = pkg_manager
        self.pkg_size = pkg_size

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(f"Uninstall [b]{self.pkg_name}[/b]?")
            yield Label(f"Manager: {self.pkg_manager}  |  Size: {self.pkg_size}")
            with Horizontal(id="confirm-buttons"):
                yield Button("Uninstall", id="btn-confirm-yes", variant="error")
                yield Button("Cancel", id="btn-confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm-yes")


class PackageManager(Widget):
    """Package manager with search, uninstall, and size info."""

    BINDINGS = [
        Binding("d", "uninstall_selected", "Uninstall", show=True),
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "clear_search", "Clear search"),
        Binding("left", "prev_manager", "Prev", show=False),
        Binding("right", "next_manager", "Next", show=False),
    ]

    _VIEWS = ["brew-view", "npm-view", "pip-view"]
    _BUTTONS = ["btn-brew", "btn-npm", "btn-pip"]
    _TABLES = ["brew-table", "npm-table", "pip-table"]

    # Store full data for filtering
    _all_rows: dict[str, list[tuple]] = {}
    _all_packages: dict[str, list[Package]] = {}
    _totals: dict[str, int] = {}
    _pending_loads: int = 0

    def compose(self) -> ComposeResult:
        with Vertical():
            # Navigation bar
            with Horizontal(id="pkg-nav"):
                yield Button("Homebrew", id="btn-brew", classes="nav-btn -active")
                yield Button("npm", id="btn-npm", classes="nav-btn")
                yield Button("pip", id="btn-pip", classes="nav-btn")
                yield Button("Refresh", id="btn-pkg-refresh", classes="nav-btn-refresh")

            # Search bar
            yield Input(placeholder="Search packages... (press / to focus)", id="pkg-search")

            # Total size indicator
            yield Label("  Loading...", id="pkg-total-size")

            # Loading indicator
            yield LoadingIndicator(id="pkg-loading")

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
            yield Label("  [d] Uninstall  [/] Search  [Esc] Clear", id="pkg-status-bar")

    def on_mount(self) -> None:
        self._all_rows = {}
        self._all_packages = {}
        self._totals = {}

        for table_id in ("brew-table", "npm-table", "pip-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns("Name", "Version", "Size", "Orphan?")
            table.cursor_type = "row"

        self._load_all()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        switcher = self.query_one(ContentSwitcher)

        nav_map = {
            "btn-brew": "brew-view",
            "btn-npm": "npm-view",
            "btn-pip": "pip-view",
        }

        if event.button.id in nav_map:
            switcher.current = nav_map[event.button.id]
            for btn in self.query(".nav-btn"):
                btn.remove_class("-active")
            event.button.add_class("-active")
            # Re-apply search filter when switching tabs
            self._apply_filter()
            # Focus the table in the new view
            table_map = {"brew-view": "brew-table", "npm-view": "npm-table", "pip-view": "pip-table"}
            table_id = table_map[nav_map[event.button.id]]
            self.set_timer(0.1, lambda tid=table_id: self.query_one(f"#{tid}", DataTable).focus())
        elif event.button.id == "btn-pkg-refresh":
            self._load_all()

    def _switch_to_view(self, index: int) -> None:
        """Switch to a manager view by index and update UI."""
        switcher = self.query_one(ContentSwitcher)
        switcher.current = self._VIEWS[index]
        for btn in self.query(".nav-btn"):
            btn.remove_class("-active")
        self.query_one(f"#{self._BUTTONS[index]}", Button).add_class("-active")
        self._apply_filter()
        table_id = self._TABLES[index]
        self.set_timer(0.1, lambda tid=table_id: self.query_one(f"#{tid}", DataTable).focus())

    def _current_view_index(self) -> int:
        current = self.query_one(ContentSwitcher).current
        return self._VIEWS.index(current) if current in self._VIEWS else 0

    def action_prev_manager(self) -> None:
        idx = (self._current_view_index() - 1) % len(self._VIEWS)
        self._switch_to_view(idx)

    def action_next_manager(self) -> None:
        idx = (self._current_view_index() + 1) % len(self._VIEWS)
        self._switch_to_view(idx)

    @on(Input.Changed, "#pkg-search")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Filter all tables by search query."""
        query = self.query_one("#pkg-search", Input).value.lower().strip()

        for table_id, rows in self._all_rows.items():
            table = self.query_one(f"#{table_id}", DataTable)
            table.clear()
            for row in rows:
                if not query or query in row[0].lower():
                    table.add_row(*row)

    def action_focus_search(self) -> None:
        self.query_one("#pkg-search", Input).focus()

    def action_clear_search(self) -> None:
        search = self.query_one("#pkg-search", Input)
        search.value = ""
        self._apply_filter()

    def action_uninstall_selected(self) -> None:
        """Uninstall the currently selected package."""
        # Find active table
        switcher = self.query_one(ContentSwitcher)
        current = switcher.current
        table_map = {
            "brew-view": ("brew-table", "homebrew"),
            "npm-view": ("npm-table", "npm"),
            "pip-view": ("pip-table", "pip"),
        }

        if current not in table_map:
            return

        table_id, manager = table_map[current]
        table = self.query_one(f"#{table_id}", DataTable)

        if table.cursor_row is None or table.row_count == 0:
            self.notify("No package selected", severity="warning")
            return

        row = table.get_row_at(table.cursor_row)
        pkg_name = str(row[0])
        pkg_size = str(row[2])

        # Show confirmation dialog
        self.app.push_screen(
            ConfirmUninstall(pkg_name, manager, pkg_size),
            callback=lambda confirmed: self._do_uninstall(confirmed, pkg_name, manager) if confirmed else None,
        )

    @work(thread=True)
    def _do_uninstall(self, confirmed: bool, pkg_name: str, manager: str) -> None:
        if not confirmed:
            return

        pkg = Package(name=pkg_name, version="", size=0, manager=manager)
        success, message = uninstall(pkg)

        if success:
            self.app.call_from_thread(
                self.notify, f"Uninstalled {pkg_name}", title="Success"
            )
            # Reload the relevant table
            reload_map = {
                "homebrew": self._load_brew,
                "npm": self._load_npm,
                "pip": self._load_pip,
            }
            if manager in reload_map:
                reload_map[manager]()
        else:
            self.app.call_from_thread(
                self.notify, f"Failed: {message}", title="Error", severity="error"
            )

    def _load_all(self) -> None:
        self._pending_loads = 3
        self.query_one("#pkg-loading").display = True
        self.query_one("#pkg-content-panel").display = False
        self.query_one("#pkg-total-size", Label).update("  Loading packages...")
        self._load_brew()
        self._load_npm()
        self._load_pip()

    @work(thread=True)
    def _load_brew(self) -> None:
        packages = list_homebrew()
        orphans = {p.name for p in find_orphans("homebrew")}
        total_size = sum(p.size for p in packages)
        sorted_pkgs = sorted(packages, key=lambda p: p.size, reverse=True)
        rows = [
            (
                pkg.name,
                pkg.version,
                humanize.naturalsize(pkg.size) if pkg.size else "-",
                "Yes" if pkg.name in orphans or pkg.is_orphan else "",
            )
            for pkg in sorted_pkgs
        ]
        self.app.call_from_thread(
            self._fill_table, "brew-table", rows, sorted_pkgs,
            f"Homebrew: {len(packages)} packages, {humanize.naturalsize(total_size)}",
            total_size,
        )

    @work(thread=True)
    def _load_npm(self) -> None:
        packages = list_npm_global()
        total_size = sum(p.size for p in packages)
        sorted_pkgs = sorted(packages, key=lambda p: p.size, reverse=True)
        rows = [
            (
                pkg.name,
                pkg.version,
                humanize.naturalsize(pkg.size) if pkg.size else "-",
                "",
            )
            for pkg in sorted_pkgs
        ]
        self.app.call_from_thread(
            self._fill_table, "npm-table", rows, sorted_pkgs,
            f"npm: {len(packages)} packages, {humanize.naturalsize(total_size)}",
            total_size,
        )

    @work(thread=True)
    def _load_pip(self) -> None:
        packages = list_pip()
        total_size = sum(p.size for p in packages)
        sorted_pkgs = sorted(packages, key=lambda p: p.size, reverse=True)
        rows = [
            (
                pkg.name,
                pkg.version,
                humanize.naturalsize(pkg.size) if pkg.size else "-",
                "",
            )
            for pkg in sorted_pkgs
        ]
        self.app.call_from_thread(
            self._fill_table, "pip-table", rows, sorted_pkgs,
            f"pip: {len(packages)} packages, {humanize.naturalsize(total_size)}",
            total_size,
        )

    def _fill_table(self, table_id: str, rows: list, packages: list, status: str, total_size: int) -> None:
        # Store full data for search filtering
        self._all_rows[table_id] = rows
        self._all_packages[table_id] = packages

        table = self.query_one(f"#{table_id}", DataTable)
        table.clear()
        for row in rows:
            table.add_row(*row)

        self._totals[table_id] = total_size
        grand_total = sum(self._totals.values())

        self.query_one("#pkg-total-size", Label).update(
            f"  Total installed: {humanize.naturalsize(grand_total)}"
        )
        self.query_one("#pkg-status-bar", Label).update(f"  {status}  |  [d] Uninstall  [/] Search")

        # Hide loading when all loads complete
        self._pending_loads -= 1
        if self._pending_loads <= 0:
            self.query_one("#pkg-loading").display = False
            self.query_one("#pkg-content-panel").display = True
