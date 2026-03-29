from __future__ import annotations

import humanize
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import DataTable, Button, Label, ContentSwitcher
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import work

from disk_analyst_tool.core.docker import (
    is_docker_available,
    list_images,
    list_containers,
    remove_image,
    remove_container,
    prune_all,
)


class ConfirmDockerAction(ModalScreen[bool]):
    """Confirmation dialog for Docker actions."""

    CSS = """
    ConfirmDockerAction {
        align: center middle;
    }
    #docker-confirm-dialog {
        width: 60;
        height: auto;
        max-height: 12;
        border: round $error;
        background: $surface;
        padding: 1 2;
    }
    #docker-confirm-dialog Label {
        width: 100%;
        margin: 0 0 1 0;
    }
    #docker-confirm-buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }
    #docker-confirm-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, title: str, detail: str) -> None:
        super().__init__()
        self._title = title
        self._detail = detail

    def compose(self) -> ComposeResult:
        with Vertical(id="docker-confirm-dialog"):
            yield Label(f"[b]{self._title}[/b]")
            yield Label(self._detail)
            with Horizontal(id="docker-confirm-buttons"):
                yield Button("Confirm", id="btn-docker-yes", variant="error")
                yield Button("Cancel", id="btn-docker-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-docker-yes")


class DockerManager(Widget):
    """Docker resource manager — images, containers, prune."""

    BINDINGS = [
        Binding("d", "remove_selected", "Remove", show=True),
        Binding("p", "prune_all", "Prune All", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            # Nav bar
            with Horizontal(id="docker-nav"):
                yield Button("Images", id="btn-docker-images", classes="nav-btn -active")
                yield Button("Containers", id="btn-docker-containers", classes="nav-btn")
                yield Button("Refresh", id="btn-docker-refresh", classes="nav-btn-refresh")
                yield Button("Prune All", id="btn-docker-prune", variant="error", classes="nav-btn-refresh")

            # Summary
            yield Label("  Loading...", id="docker-summary")

            # Content
            with Vertical(id="docker-content-panel", classes="panel"):
                with ContentSwitcher(initial="images-view"):
                    with Vertical(id="images-view"):
                        yield DataTable(id="docker-images-table")
                    with Vertical(id="containers-view"):
                        yield DataTable(id="docker-containers-table")

            # Status
            yield Label("  [d] Remove  [p] Prune All", id="docker-status-bar")

    def on_mount(self) -> None:
        img_table = self.query_one("#docker-images-table", DataTable)
        img_table.add_columns("Repository", "Tag", "ID", "Size", "Created")
        img_table.cursor_type = "row"

        ctr_table = self.query_one("#docker-containers-table", DataTable)
        ctr_table.add_columns("Name", "Image", "Status", "ID")
        ctr_table.cursor_type = "row"

        self._check_and_load()

    def _check_and_load(self) -> None:
        self._load_data()

    @work(thread=True)
    def _load_data(self) -> None:
        if not is_docker_available():
            self.app.call_from_thread(
                self._show_unavailable
            )
            return

        images = list_images()
        containers = list_containers()

        img_rows = [
            (
                img.repository,
                img.tag,
                img.image_id[:12],
                humanize.naturalsize(img.size),
                img.created,
            )
            for img in images
        ]

        ctr_rows = [
            (
                ctr.name,
                ctr.image,
                ctr.status,
                ctr.container_id[:12],
            )
            for ctr in containers
        ]

        total_img_size = sum(img.size for img in images)

        self.app.call_from_thread(
            self._render_data, img_rows, ctr_rows, len(images), len(containers), total_img_size
        )

    def _show_unavailable(self) -> None:
        self.query_one("#docker-summary", Label).update(
            "  Docker is not running or not installed"
        )

    def _render_data(
        self, img_rows: list, ctr_rows: list,
        img_count: int, ctr_count: int, total_size: int,
    ) -> None:
        img_table = self.query_one("#docker-images-table", DataTable)
        img_table.clear()
        for row in img_rows:
            img_table.add_row(*row)

        ctr_table = self.query_one("#docker-containers-table", DataTable)
        ctr_table.clear()
        for row in ctr_rows:
            ctr_table.add_row(*row)

        self.query_one("#docker-summary", Label).update(
            f"  Images: {img_count} ({humanize.naturalsize(total_size)})  |  Containers: {ctr_count}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        switcher = self.query_one(ContentSwitcher)

        nav_map = {
            "btn-docker-images": "images-view",
            "btn-docker-containers": "containers-view",
        }

        if event.button.id in nav_map:
            switcher.current = nav_map[event.button.id]
            for btn in self.query(".nav-btn"):
                btn.remove_class("-active")
            event.button.add_class("-active")
            # Focus the table in the new view
            table_map = {"images-view": "docker-images-table", "containers-view": "docker-containers-table"}
            table_id = table_map[nav_map[event.button.id]]
            self.set_timer(0.1, lambda tid=table_id: self.query_one(f"#{tid}", DataTable).focus())
        elif event.button.id == "btn-docker-refresh":
            self._check_and_load()
        elif event.button.id == "btn-docker-prune":
            self.action_prune_all()

    def action_remove_selected(self) -> None:
        switcher = self.query_one(ContentSwitcher)

        if switcher.current == "images-view":
            table = self.query_one("#docker-images-table", DataTable)
            if table.cursor_row is None or table.row_count == 0:
                self.notify("No image selected", severity="warning")
                return
            row = table.get_row_at(table.cursor_row)
            name = f"{row[0]}:{row[1]}"
            image_id = str(row[2])
            self.app.push_screen(
                ConfirmDockerAction(f"Remove image {name}?", f"ID: {image_id}"),
                callback=lambda ok: self._do_remove_image(image_id) if ok else None,
            )
        elif switcher.current == "containers-view":
            table = self.query_one("#docker-containers-table", DataTable)
            if table.cursor_row is None or table.row_count == 0:
                self.notify("No container selected", severity="warning")
                return
            row = table.get_row_at(table.cursor_row)
            name = str(row[0])
            ctr_id = str(row[3])
            self.app.push_screen(
                ConfirmDockerAction(f"Remove container {name}?", f"ID: {ctr_id}"),
                callback=lambda ok: self._do_remove_container(ctr_id) if ok else None,
            )

    @work(thread=True)
    def _do_remove_image(self, image_id: str) -> None:
        success, msg = remove_image(image_id, force=True)
        if success:
            self.app.call_from_thread(self.notify, f"Removed image {image_id}", title="Success")
        else:
            self.app.call_from_thread(self.notify, f"Failed: {msg}", title="Error", severity="error")
        self._load_data()

    @work(thread=True)
    def _do_remove_container(self, container_id: str) -> None:
        success, msg = remove_container(container_id, force=True)
        if success:
            self.app.call_from_thread(self.notify, f"Removed container {container_id}", title="Success")
        else:
            self.app.call_from_thread(self.notify, f"Failed: {msg}", title="Error", severity="error")
        self._load_data()

    def action_prune_all(self) -> None:
        self.app.push_screen(
            ConfirmDockerAction(
                "Prune all unused Docker resources?",
                "This removes stopped containers, unused networks, dangling images, and build cache.",
            ),
            callback=lambda ok: self._do_prune() if ok else None,
        )

    @work(thread=True)
    def _do_prune(self) -> None:
        result = prune_all()
        if result.errors:
            self.app.call_from_thread(
                self.notify, f"Errors: {result.errors[0]}", title="Prune failed", severity="error"
            )
        else:
            self.app.call_from_thread(
                self.notify,
                f"Freed {humanize.naturalsize(result.space_freed)}",
                title="Prune complete",
            )
        self._load_data()
