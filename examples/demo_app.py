#!/usr/bin/env python3
"""
Demo app for textual-cmdorc.

Uses the real cmdorc v0.2.1+ package and demonstrates all features:
- Keyboard shortcuts with help screen
- Command execution (click tree nodes)
- Tooltips on commands (via CmdorcView)
- Auto-expanded tree
- Log pane toggle
"""

import sys
from pathlib import Path

# Clean up any test mocks from sys.modules to ensure we use real cmdorc
if "cmdorc" in sys.modules:
    del sys.modules["cmdorc"]

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from textual_cmdorc import CmdorcController, CmdorcView, HelpScreen, KeyboardHandler


class StatusPanel(Static):
    """Real-time status display."""

    status = reactive("Demo Mode - Ready")

    def render(self):
        return f"[bold green]Status:[/] {self.status}"


class DemoDashboard(App):
    """Demo dashboard showcasing textual-cmdorc embedding."""

    TITLE = "textual-cmdorc Demo"
    BINDINGS = [
        Binding("h", "show_help", "Help"),
        Binding("l", "toggle_log", "Toggle Log"),
        Binding("r", "reload_config", "Reload"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    CmdorcView {
        height: 1fr;
    }

    #status {
        dock: bottom;
        height: 3;
        background: $boost;
        border-top: solid $primary;
    }

    #help-modal {
        border: solid $primary;
    }

    .help-header {
        background: $primary;
        color: $text;
        padding: 1 2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.controller = None
        self.view = None
        self.keyboard_handler = None
        self._show_log = True

    def compose(self) -> ComposeResult:
        yield Header()

        # Create a demo config for testing
        config_path = Path(__file__).parent.parent / "config.toml"
        if not config_path.exists():
            print(f"Creating demo config at {config_path}...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("""
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3", "Another Command" = "4" }
enabled = true

[[command]]
name = "Lint"
command = "echo '📝 Linting...'"
triggers = []

[[command]]
name = "Format"
command = "echo '✨ Formatting...'"
triggers = ["command_success:Lint"]

[[command]]
name = "Tests"
command = "echo '🧪 Running tests...'"
triggers = ["command_success:Format"]

[[command]]
name = "Another Command"
command = "echo '🔧 Running another command...'"
triggers = []
""")

        self.controller = CmdorcController(str(config_path), enable_watchers=False)
        self.view = CmdorcView(self.controller, show_log_pane=self._show_log)
        yield self.view

        yield StatusPanel(id="status")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on app mount."""
        status_panel = self.query_one("#status", StatusPanel)
        try:
            loop = asyncio.get_running_loop()
            self.controller.attach(loop)

            # Initialize keyboard handler for shortcuts
            self.keyboard_handler = KeyboardHandler(self.controller, app=self)
            callbacks = self.keyboard_handler.bind_all()
            if callbacks:
                status_panel.status = f"✓ Demo initialized - {len(callbacks)} shortcuts - Press 'h' for help"
            else:
                status_panel.status = "✓ Demo initialized - Press 'h' for help"

            # Wire events
            self.controller.on_command_started = self._on_command_started
            self.controller.on_command_finished = self._on_command_finished

            # Expand all top-level tree nodes
            self._expand_tree()

        except Exception as e:
            status_panel.status = f"✗ Error: {e}"

    def _expand_tree(self) -> None:
        """Expand all top-level tree nodes."""
        try:
            from textual.widgets import Tree

            tree = self.view.query_one(Tree)
            # Expand root and all first-level children
            tree.root.expand()
            for node in tree.root.children:
                node.expand()
        except Exception:
            pass  # Ignore if tree structure is different

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if hasattr(self, "controller") and self.controller:
            self.controller.detach()

    def _on_command_started(self, name: str, _trigger_source) -> None:
        """Handle command start."""
        status_panel = self.query_one("#status", StatusPanel)
        status_panel.status = f"▶ Running {name}..."

    def _on_command_finished(self, name: str, _result) -> None:
        """Handle command completion."""
        status_panel = self.query_one("#status", StatusPanel)
        status_panel.status = f"✓ {name} finished"

    async def action_show_help(self) -> None:
        """Show help screen with keyboard shortcuts."""
        if self.controller:
            help_screen = HelpScreen(
                keyboard_config=self.controller.keyboard_config,
                keyboard_conflicts=self.controller.keyboard_conflicts,
                keyboard_handler=self.keyboard_handler,
            )
            await self.push_screen(help_screen)

    async def action_toggle_log(self) -> None:
        """Toggle log pane visibility."""
        self._show_log = not self._show_log
        if self.view:
            # Recreate view with new log pane setting
            old_view = self.view
            self.view = CmdorcView(self.controller, show_log_pane=self._show_log)
            await self.mount(self.view, before=old_view)
            await old_view.remove()
            self._expand_tree()

        status_panel = self.query_one("#status", StatusPanel)
        status_panel.status = f"Log pane {'shown' if self._show_log else 'hidden'}"

    async def action_reload_config(self) -> None:
        """Reload configuration."""
        if self.view:
            self.view.refresh_tree()
            self._expand_tree()

        status_panel = self.query_one("#status", StatusPanel)
        status_panel.status = "✓ Configuration reloaded"


if __name__ == "__main__":
    print("Starting textual-cmdorc demo...")
    print("Press 'q' to quit, 'h' for help, 'l' to toggle log, 'r' to reload")
    print("Keyboard shortcuts: 1=Lint, 2=Format, 3=Tests, 4=Another Command")
    app = DemoDashboard()
    app.run()
