#!/usr/bin/env python3
"""
Demo app for textual-cmdorc.

Uses the real cmdorc v0.2.1+ package.
"""

import sys
from pathlib import Path

# Clean up any test mocks from sys.modules to ensure we use real cmdorc
if 'cmdorc' in sys.modules:
    del sys.modules['cmdorc']

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncio
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.reactive import reactive

from textual_cmdorc import CmdorcController, CmdorcView


class StatusPanel(Static):
    """Real-time status display."""

    status = reactive("Demo Mode - Ready")

    def render(self):
        return f"[bold green]Status:[/] {self.status}"


class DemoDashboard(App):
    """Demo dashboard showcasing textual-cmdorc embedding."""

    TITLE = "textual-cmdorc Demo"
    BINDINGS = [("q", "quit", "Quit")]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #status {
        dock: bottom;
        height: 3;
        background: $boost;
        border-top: solid $primary;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()

        # Create a demo config for testing
        config_path = Path(__file__).parent.parent / "config.toml"
        if not config_path.exists():
            print(f"Creating demo config at {config_path}...")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("""
[keyboard]
shortcuts = { Demo = "1", Status = "2" }
enabled = true

[[command]]
name = "Demo"
command = "echo 'Demo command'"
triggers = []

[[command]]
name = "Status"
command = "echo 'Status check'"
triggers = ["command_success:Demo"]
""")

        self.controller = CmdorcController(str(config_path), enable_watchers=False)

        yield Horizontal(
            CmdorcView(self.controller, show_log_pane=True),
            id="main",
        )

        yield StatusPanel(id="status")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on app mount."""
        status_panel = self.query_one("#status", StatusPanel)
        try:
            loop = asyncio.get_running_loop()
            self.controller.attach(loop)
            status_panel.status = "✓ Demo initialized - Press 'h' for help"

            # Wire events
            self.controller.on_command_finished = self._on_command_finished
        except Exception as e:
            status_panel.status = f"✗ Error: {e}"

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if hasattr(self, "controller"):
            self.controller.detach()

    def _on_command_finished(self, name: str, result):
        """Handle command completion."""
        status_panel = self.query_one("#status", StatusPanel)
        status_panel.status = f"✓ {name} finished"


if __name__ == "__main__":
    print("Starting textual-cmdorc demo...")
    print("Press 'q' to quit, 'h' for help")
    app = DemoDashboard()
    app.run()
