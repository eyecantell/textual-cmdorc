#!/usr/bin/env python3
"""
Example: Development Dashboard
Shows how to embed cmdorc in a monitoring dashboard with multiple pipelines.

This example demonstrates:
- Multiple CmdorcController instances for different workflows
- Event handling and status aggregation
- Custom button integration
- Tabbed interface with separate command panels
"""

import asyncio

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

# Import from textual-cmdorc
try:
    from textual_cmdorc import CmdorcController, CmdorcView
except ImportError:
    print("Error: Install textual-cmdorc first: pip install textual-cmdorc")
    exit(1)


class StatusPanel(Static):
    """Real-time status display."""

    status = reactive("Initializing...")

    def render(self):
        return f"[bold green]Status:[/] {self.status}"


class DevDashboard(App):
    """
    Development dashboard embedding multiple cmdorc pipelines.

    Demonstrates:
    - Multiple independent workflows
    - Event-driven architecture
    - Custom UI integration with cmdorc
    """

    TITLE = "Dev Dashboard - Command Orchestration"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "demo_workflow", "Run Demo"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #tabs {
        height: 1fr;
        border: solid $primary;
    }

    TabPane {
        layout: vertical;
    }

    #status-panel {
        dock: bottom;
        height: 3;
        background: $boost;
        border-top: solid $primary;
    }

    .button-group {
        height: auto;
        width: 40;
    }

    Button {
        margin: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the dashboard layout."""
        yield Header()

        # Create a controller for each workflow
        # (In real usage, these would load from separate config files)
        self.lint_ctrl = CmdorcController("config.toml", enable_watchers=False)
        self.test_ctrl = CmdorcController("config.toml", enable_watchers=False)
        self.build_ctrl = CmdorcController("config.toml", enable_watchers=False)

        # Main tabbed interface
        with TabbedContent(id="tabs"):
            with TabPane("Lint Pipeline", id="lint-tab"):
                yield CmdorcView(self.lint_ctrl, show_log_pane=True)

            with TabPane("Test Pipeline", id="test-tab"):
                yield CmdorcView(self.test_ctrl, show_log_pane=True)

            with TabPane("Build Pipeline", id="build-tab"):
                yield CmdorcView(self.build_ctrl, show_log_pane=True)

        # Status panel at bottom
        yield StatusPanel(id="status-panel")

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize controllers and wire callbacks."""
        loop = asyncio.get_running_loop()

        # Attach all controllers to the event loop
        for controller in [self.lint_ctrl, self.test_ctrl, self.build_ctrl]:
            controller.attach(loop)
            # Wire events to our handlers
            controller.on_command_started = self._on_command_started
            controller.on_command_finished = self._on_command_finished

        # Get status panel
        self.status_panel = self.query_one("#status-panel", StatusPanel)
        self.status_panel.status = "Ready"

        self.notify("Dashboard initialized. Press 'd' to run demo.")

    async def on_unmount(self) -> None:
        """Cleanup controllers."""
        for controller in [self.lint_ctrl, self.test_ctrl, self.build_ctrl]:
            controller.detach()

    def _on_command_started(self, name: str, trigger):
        """Handle command start."""
        self.status_panel.status = f"▶ {name} started..."

    def _on_command_finished(self, name: str, result):
        """Handle command completion."""
        status = "✓" if result.state.value == "success" else "✗"
        self.status_panel.status = f"{status} {name} → {result.state.value}"
        self.notify(f"{status} {name} finished")

    def action_demo_workflow(self) -> None:
        """Run a demo workflow."""
        self.status_panel.status = "▶ Running demo workflow..."
        # In a real app, you'd trigger actual commands
        self.notify("Demo: Starting Lint")


if __name__ == "__main__":
    app = DevDashboard()
    app.run()
