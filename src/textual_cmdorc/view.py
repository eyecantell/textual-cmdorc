"""Textual widget for rendering cmdorc command list. Suitable for embedding."""

from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Log

from textual_cmdorc.controller import CmdorcController


class CmdorcView(Widget):
    """Textual widget for rendering cmdorc command list with indentation. Suitable for embedding."""

    DEFAULT_CSS = """
    CmdorcView {
        height: 1fr;
    }

    CmdorcView > VerticalScroll {
        height: 1fr;
    }

    CmdorcView > Log {
        height: 10;
    }
    """

    def __init__(
        self,
        controller: CmdorcController | None,
        show_log_pane: bool = True,
        enable_local_bindings: bool = False,
    ):
        """Initialize view.

        Args:
            controller: CmdorcController instance (can be None initially)
            show_log_pane: Whether to render log pane
            enable_local_bindings: If True, handle keys when focused (standalone only)
        """
        super().__init__()
        self._controller = controller
        self.show_log_pane = show_log_pane
        self.enable_local_bindings = enable_local_bindings
        # FIX #2: Track all instances of each command to detect duplicates
        self._command_widgets: dict[str, list] = {}
        self.log_pane: Log | None = None

    @property
    def controller(self) -> CmdorcController | None:
        """Get the controller."""
        return self._controller

    @controller.setter
    def controller(self, value: CmdorcController | None) -> None:
        """Set the controller and rebuild list if needed."""
        self._controller = value
        # If view is already mounted and controller is now set, rebuild the list
        if value is not None and self.is_mounted:
            try:
                container = self.query_one("#command-list", Vertical)
                container.remove_children()
                self._build_command_list(container, value.hierarchy, indent=0)
            except Exception:
                # Silently fail if container doesn't exist yet
                pass

    def compose(self):
        """Compose command list and optional log pane."""
        with VerticalScroll(id="commands-container"):
            yield Vertical(id="command-list")

        # Optional log pane
        if self.show_log_pane:
            self.log_pane = Log(id="log-pane")
            yield self.log_pane

    def on_mount(self) -> None:
        """Build command list from controller.hierarchy."""
        # Handle case where controller might be None during initial mount
        if self.controller is None:
            return
        container = self.query_one("#command-list", Vertical)
        self._build_command_list(container, self.controller.hierarchy, indent=0)

    def _build_command_list(self, container, nodes, indent=0):
        """Recursively build command list with indentation.

        FIX #2: Tracks command occurrences to detect duplicates and mark them.

        Args:
            container: Vertical container to add widgets to
            nodes: List of CommandNode to render
            indent: Indentation level (0, 1, 2, ...)
        """
        from textual_cmdorc.integrator import create_command_widget

        for node in nodes:
            # Get keyboard shortcut for this command
            shortcut = (
                self.controller.keyboard_config.shortcuts.get(node.name)
                if self.controller.keyboard_config.enabled
                else None
            )

            # FIX #2: Detect if this is a duplicate (appeared before)
            occurrence_count = len(self._command_widgets.get(node.name, []))
            is_duplicate = occurrence_count > 0

            # Create command widget with indentation and duplicate indicator
            widget = create_command_widget(
                node,
                self.controller.orchestrator,
                keyboard_shortcut=shortcut,
                indent=indent,
                is_duplicate=is_duplicate,
            )

            # FIX #2: Store all instances of this command
            if node.name not in self._command_widgets:
                self._command_widgets[node.name] = []
            self._command_widgets[node.name].append(widget)

            # Add to container
            container.mount(widget)

            # Recursively add children with more indentation
            if node.children:
                self._build_command_list(container, node.children, indent + 1)

    def refresh_tree(self) -> None:
        """Rebuild list from controller.hierarchy."""
        container = self.query_one("#command-list", Vertical)
        container.remove_children()
        self._command_widgets.clear()
        self._build_command_list(container, self.controller.hierarchy, indent=0)

    def update_command(self, name: str, update) -> None:
        """Update display of specific command.

        Args:
            name: Command name
            update: PresentationUpdate with new display state
        """
        if name in self._command_widgets:
            for widget in self._command_widgets[name]:
                if hasattr(widget, "set_status"):
                    widget.set_status(
                        icon=update.icon,
                        tooltip=update.tooltip,
                        running=update.running,
                    )

                    if update.output_path:
                        from pathlib import Path
                        widget.set_output_path(
                            Path(update.output_path),
                            tooltip="Click to view output",
                        )
