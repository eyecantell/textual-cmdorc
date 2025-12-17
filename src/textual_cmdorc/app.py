"""Standalone TUI application for textual-cmdorc.

Thin shell composing CmdorcController + CmdorcView.
For embedding, use CmdorcController + CmdorcView directly in your app.
"""

import asyncio
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical

from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.view import CmdorcView
from cmdorc_frontend.models import ConfigValidationResult, KeyboardConfig

logger = logging.getLogger(__name__)


class HelpScreen(ModalScreen):
    """Modal help screen showing keyboard shortcuts and conflicts.

    FIX #6: Use ModalScreen instead of log pane for help.
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, keyboard_config: KeyboardConfig, keyboard_conflicts: dict):
        """Initialize help screen.

        Args:
            keyboard_config: KeyboardConfig with shortcuts
            keyboard_conflicts: Dict of conflicting keys
        """
        super().__init__()
        self.keyboard_config = keyboard_config
        self.keyboard_conflicts = keyboard_conflicts

    def compose(self) -> ComposeResult:
        """Compose help content."""
        yield Static("Keyboard Shortcuts", classes="help-header")

        # Shortcuts
        if self.keyboard_config.shortcuts:
            content = "App Shortcuts:\n"
            content += "  [h] — Show help\n"
            content += "  [r] — Reload config\n"
            content += "  [l] — Toggle log pane\n"
            content += "  [q] — Quit\n\n"

            content += "Command Shortcuts:\n"
            for cmd_name, key in self.keyboard_config.shortcuts.items():
                marker = " ⚠ (conflict)" if key in self.keyboard_conflicts else ""
                content += f"  [{key}] — {cmd_name}{marker}\n"

            yield Static(content)
        else:
            yield Static("No keyboard shortcuts configured.")

        # Conflicts
        if self.keyboard_conflicts:
            conflict_info = "\nConflicting Keys:\n"
            for key, commands in self.keyboard_conflicts.items():
                conflict_info += f"  [{key}] assigned to: {', '.join(commands)}\n"
                conflict_info += f"       → First one wins\n"
            yield Static(conflict_info)


class CmdorcApp(App):
    """Thin shell for standalone mode (not embeddable).

    For embedding, use CmdorcController + CmdorcView directly.

    Design Principles (Anti-patterns to avoid - FIX #7):
    - ❌ Do not bind global keys inside the controller
    - ❌ Do not call `exit()` or `app.exit()` from controller
    - ❌ Do not poll orchestrator state (use callbacks only)
    - ❌ Do not make controller depend on Textual
    - ❌ Do not auto-start watchers without checking `enable_watchers`
    """

    TITLE = "cmdorc"
    BINDINGS = [
        Binding("h", "show_help", "Help"),
        Binding("r", "reload_config", "Reload"),
        Binding("l", "toggle_log", "Toggle Log"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    CmdorcView {
        height: 1fr;
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

    def __init__(self, config_path: str = "config.toml", **kwargs):
        """Initialize app.

        Args:
            config_path: Path to TOML config file
        """
        super().__init__(**kwargs)
        self.config_path = Path(config_path)
        self.controller: CmdorcController | None = None
        self.view: CmdorcView | None = None
        self._show_log = True

    def compose(self) -> ComposeResult:
        """Compose app layout."""
        yield Header()
        self.view = CmdorcView(self.controller, show_log_pane=self._show_log)
        yield self.view
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize controller and attach to event loop.

        RECOMMENDATION #3: Get validation from controller, display only.
        Should-fix #2: Only show validation summary if warnings/errors exist.
        """
        try:
            # Create controller
            self.controller = CmdorcController(
                self.config_path,
                enable_watchers=True,  # Auto-start watchers in standalone mode
            )

            # Wire validation callback
            if hasattr(self.controller, "on_validation_result"):
                self.controller.on_validation_result = self._on_validation_result

            # Attach to event loop
            loop = asyncio.get_running_loop()
            self.controller.attach(loop)

            # Update view with controller
            if self.view:
                self.view.controller = self.controller

            # RECOMMENDATION #3: Get validation and display only
            validation = self.controller.validate_config()
            if validation.warnings or validation.errors:
                self._display_validation_summary(validation)

            logger.info("CmdorcApp mounted successfully")
        except Exception as e:
            logger.error(f"Failed to mount app: {e}")
            self.exit(message=f"Error: {e}")

    def _on_validation_result(self, result: ConfigValidationResult) -> None:
        """Handle validation results from controller.

        Args:
            result: ConfigValidationResult
        """
        if result.warnings or result.errors:
            self._display_validation_summary(result)

    def _display_validation_summary(self, result: ConfigValidationResult) -> None:
        """Display validation summary in log pane or title.

        Args:
            result: ConfigValidationResult
        """
        logger.info(
            f"Config loaded: {result.commands_loaded} commands, "
            f"{result.watchers_active} watchers"
        )
        for warning in result.warnings:
            logger.warning(f"⚠ {warning}")
        for error in result.errors:
            logger.error(f"❌ {error}")

    async def on_unmount(self) -> None:
        """Cleanup controller on exit."""
        if self.controller:
            self.controller.detach()

    async def action_quit(self) -> None:
        """Quit application.

        FIX #7: App action, not controller action.
        """
        self.exit()

    async def action_reload_config(self) -> None:
        """Reload configuration from disk."""
        if not self.controller:
            logger.warning("Controller not initialized")
            return

        try:
            await self.controller.reload_config()
            logger.info("Configuration reloaded")

            # Refresh view
            if self.view:
                self.view.refresh_tree()
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")

    async def action_cancel_all(self) -> None:
        """Cancel all running commands."""
        if not self.controller:
            return

        try:
            for node in self.controller.hierarchy:
                await self.controller.cancel_command(node.name)
        except Exception as e:
            logger.error(f"Error cancelling commands: {e}")

    def action_toggle_log(self) -> None:
        """Toggle log pane visibility.

        Note: Requires full re-compose in current Textual version.
        """
        self._show_log = not self._show_log
        logger.info(f"Log pane {'shown' if self._show_log else 'hidden'}")

    def action_show_help(self) -> None:
        """Show help screen with keyboard shortcuts and conflicts.

        FIX #6: Uses ModalScreen instead of log pane.
        """
        if not self.controller:
            return

        help_screen = HelpScreen(
            self.controller.keyboard_config,
            self.controller.keyboard_conflicts,
        )
        self.push_screen(help_screen)


def main(config_path: str = "config.toml") -> None:
    """Run standalone app.

    Args:
        config_path: Path to TOML config file
    """
    app = CmdorcApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
