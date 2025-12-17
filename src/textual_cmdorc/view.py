"""Textual widget for rendering cmdorc command tree. Suitable for embedding."""

from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Log, Tree

from textual_cmdorc.controller import CmdorcController


class CmdorcView(Widget):
    """Textual widget for rendering cmdorc command tree. Suitable for embedding."""

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
        self._command_links: dict[str, list] = {}
        self._command_nodes: dict[str, list] = {}  # Store tree node references
        self.log_pane: Log | None = None

    @property
    def controller(self) -> CmdorcController | None:
        """Get the controller."""
        return self._controller

    @controller.setter
    def controller(self, value: CmdorcController | None) -> None:
        """Set the controller and rebuild tree if needed."""
        self._controller = value
        # If view is already mounted and controller is now set, rebuild the tree
        if value is not None and self.is_mounted:
            try:
                tree = self.query_one("#command-tree", Tree)
                tree.clear()
                self._build_tree(tree, value.hierarchy)
            except Exception:
                # Silently fail if tree doesn't exist yet
                pass

    def compose(self):
        """Compose tree and optional log pane."""
        with VerticalScroll(id="tree-container"):
            yield Tree("Commands", id="command-tree")

        # Optional log pane
        if self.show_log_pane:
            self.log_pane = Log(id="log-pane")
            yield self.log_pane

    def on_mount(self) -> None:
        """Build command tree from controller.hierarchy."""
        # Handle case where controller might be None during initial mount
        if self.controller is None:
            return
        tree = self.query_one("#command-tree", Tree)
        self._build_tree(tree, self.controller.hierarchy)

    def _build_tree(self, tree, nodes, parent=None):
        """Recursively build tree from CommandNode hierarchy.

        FIX #2: Tracks command occurrences to detect duplicates and mark them.
        """
        from textual_cmdorc.integrator import create_command_link

        for node in nodes:
            # Get keyboard shortcut for this command
            shortcut = (
                self.controller.keyboard_config.shortcuts.get(node.name)
                if self.controller.keyboard_config.enabled
                else None
            )

            # FIX #2: Detect if this is a duplicate (appeared before)
            occurrence_count = len(self._command_links.get(node.name, []))
            is_duplicate = occurrence_count > 0

            # Create link with shortcut and duplicate indicator
            link = create_command_link(node, self.controller.orchestrator, keyboard_shortcut=shortcut)
            link.is_duplicate = is_duplicate  # FIX #2: Mark duplicates

            # FIX #2: Store all instances of this command
            if node.name not in self._command_links:
                self._command_links[node.name] = []
            self._command_links[node.name].append(link)

            # Refresh tooltips to reflect duplicate status
            if hasattr(link, "_update_tooltips"):
                link._update_tooltips()

            # Add to tree
            if parent is None:
                tree.root.label = "Commands"
                tree_node = tree.root.add(link.get_label(), data=link)
            else:
                tree_node = parent.add(link.get_label(), data=link)

            # Store tree node reference for updates
            if node.name not in self._command_nodes:
                self._command_nodes[node.name] = []
            self._command_nodes[node.name].append(tree_node)

            # Recursively add children
            if node.children:
                self._build_tree(tree, node.children, tree_node)

    def refresh_tree(self) -> None:
        """Rebuild tree from controller.hierarchy."""
        tree = self.query_one("#command-tree", Tree)
        tree.clear()
        self._command_links.clear()
        self._command_nodes.clear()
        self._build_tree(tree, self.controller.hierarchy)

    def update_command(self, name: str, update) -> None:
        """Update display of specific command.

        Args:
            name: Command name
            update: PresentationUpdate with new display state
        """
        if name in self._command_links:
            for i, link in enumerate(self._command_links[name]):
                if hasattr(link, "apply_update"):
                    link.apply_update(update)
                # Update tree node label to reflect new status
                if name in self._command_nodes and i < len(self._command_nodes[name]):
                    self._command_nodes[name][i].label = link.get_label()
