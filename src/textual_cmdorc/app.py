"""Standalone TUI application for textual-cmdorc.

Thin shell composing CmdorcController + CmdorcView.
For embedding, use CmdorcController + CmdorcView directly in your app.
"""

import asyncio
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static
from textual_filelink import CommandLink

from cmdorc_frontend.models import ConfigValidationResult, KeyboardConfig
from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.keyboard_handler import KeyboardHandler
from textual_cmdorc.view import CmdorcView
from textual_cmdorc.widgets import CmdorcCommandLink

logger = logging.getLogger(__name__)


class HelpScreen(ModalScreen):
    """Modal help screen showing keyboard shortcuts, conflicts, and tips.

    FIX #6: Use ModalScreen instead of log pane for help.
    Includes keyboard conflict detection (FIX #3) and helpful tips.
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        keyboard_config: KeyboardConfig,
        keyboard_conflicts: dict,
        keyboard_handler: "KeyboardHandler | None" = None,
    ):
        """Initialize help screen.

        Args:
            keyboard_config: KeyboardConfig with shortcuts
            keyboard_conflicts: Dict of conflicting keys (FIX #3)
            keyboard_handler: Optional KeyboardHandler for detailed info
        """
        super().__init__()
        self.keyboard_config = keyboard_config
        self.keyboard_conflicts = keyboard_conflicts
        self.keyboard_handler = keyboard_handler

    def compose(self) -> ComposeResult:
        """Compose help content with sections."""
        # Header
        yield Static("Command Line TUI - Keyboard Help", classes="help-header")

        # App shortcuts
        app_shortcuts = (
            "Application Shortcuts:\n"
            "  [h] — Show this help screen\n"
            "  [r] — Reload configuration\n"
            "  [l] — Toggle log pane\n"
            "  [q] — Quit application"
        )
        yield Static(app_shortcuts)

        # Command shortcuts
        if self.keyboard_config.shortcuts:
            yield Static("Command Shortcuts:", classes="help-header")

            content = ""
            for cmd_name, key in sorted(self.keyboard_config.shortcuts.items()):
                if key in self.keyboard_conflicts:
                    # Mark conflicting commands
                    conflicting = [c for c in self.keyboard_conflicts[key] if c != cmd_name]
                    if conflicting:
                        content += f"  [{key}] → {cmd_name} ⚠ (also: {', '.join(conflicting)})\n"
                    else:
                        content += f"  [{key}] → {cmd_name}\n"
                else:
                    content += f"  [{key}] → {cmd_name}\n"

            yield Static(content)
        else:
            yield Static("No command shortcuts configured.", classes="help-header")

        # Keyboard conflicts (FIX #3)
        if self.keyboard_conflicts:
            yield Static("Keyboard Conflicts (FIX #3):", classes="help-header")

            conflict_info = ""
            for key, commands in sorted(self.keyboard_conflicts.items()):
                conflict_info += f"  [{key}] assigned to: {', '.join(commands)}\n"
                conflict_info += "       → First command wins, others are shadowed\n"

            yield Static(conflict_info)

        # Tips
        yield Static("Tips:", classes="help-header")

        tips = (
            "• Duplicate commands appear in multiple places (marked with ↳)\n"
            "• Keyboard shortcuts affect all instances of a command\n"
            "• Add shortcuts in config: [keyboard] section\n"
            "• Valid keys: 1-9, a-z, f1-f12\n"
            "• Conflicts resolved alphabetically (first one wins)"
        )
        yield Static(tips)


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

    #commands-container {
        height: 1fr;
        border: solid $accent;
    }

    #command-list {
        width: 100%;
        height: auto;
    }

    /* CommandLink styling */
    CmdorcCommandLink {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
    }

    CmdorcCommandLink CommandLink {
        width: 100%;
    }

    /* Indentation styling */
    CmdorcCommandLink .indent {
        color: $text-muted;
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
        self.keyboard_handler: KeyboardHandler | None = None
        self._show_log = True

    def compose(self) -> ComposeResult:
        """Compose app layout."""
        yield Header()
        self.view = CmdorcView(self.controller, show_log_pane=self._show_log)
        yield self.view
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize controller, keyboard handler, and attach to event loop.

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

            # Initialize keyboard handler (FIX #1: sync-safe binding)
            self.keyboard_handler = KeyboardHandler(self.controller, app=self)
            callbacks = self.keyboard_handler.bind_all()

            if callbacks:
                logger.info(f"Bound {len(callbacks)} keyboard shortcuts")

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
        logger.info(f"Config loaded: {result.commands_loaded} commands, {result.watchers_active} watchers")
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
        FIX #3: Shows keyboard conflicts and how to resolve them.
        """
        if not self.controller:
            return

        help_screen = HelpScreen(
            self.controller.keyboard_config,
            self.controller.keyboard_conflicts,
            keyboard_handler=self.keyboard_handler,
        )
        self.push_screen(help_screen)

    def action_command(self, command_name: str) -> None:
        """Execute a command by name via keyboard shortcut.

        This action is called when keyboard shortcuts are triggered via
        KeyboardHandler bindings like "command(Lint)".

        Args:
            command_name: Name of command to execute (e.g., "Lint", "Format")
        """
        if self.controller:
            # Use request_run (sync-safe) since this is called from UI context
            self.controller.request_run(command_name)
        else:
            logger.warning(f"Cannot run command '{command_name}': controller not initialized")

    def on_key(self, event: Key) -> None:
        """Route number keys to commands - triggers play/stop toggle.

        This allows keyboard shortcuts to work globally without focus.
        Number keys 1-9, a-z, f1-f12 can trigger commands.

        Args:
            event: Key event
        """
        if not self.controller:
            return

        # Get keyboard hints (mapping of key -> command_name)
        keyboard_hints = self.controller.keyboard_hints

        if event.key in keyboard_hints:
            command_name = keyboard_hints[event.key]

            # Find the command widget and toggle its play/stop state
            if self.view:
                if command_name in self.view._command_widgets:
                    for widget in self.view._command_widgets[command_name]:
                        if isinstance(widget, CmdorcCommandLink):
                            # Toggle play/stop via the command_link widget
                            if hasattr(widget.command_link, "action_play_stop"):
                                widget.command_link.action_play_stop()
                            event.prevent_default()
                            return

    def on_command_link_play_clicked(self, message: CommandLink.PlayClicked) -> None:
        """Handle play button clicks - start command execution.

        Args:
            message: CommandLink.PlayClicked message
        """
        if self.controller:
            # Use request_run (sync-safe)
            self.controller.request_run(message.name)

    def on_command_link_stop_clicked(self, message: CommandLink.StopClicked) -> None:
        """Handle stop button clicks - cancel command execution.

        Args:
            message: CommandLink.StopClicked message
        """
        if self.controller:
            # Use request_cancel (sync-safe)
            self.controller.request_cancel(message.name)

    def on_command_link_settings_clicked(self, message: CommandLink.SettingsClicked) -> None:
        """Handle settings icon clicks - show command settings menu.

        Args:
            message: CommandLink.SettingsClicked message
        """
        # TODO: Implement settings menu in future
        self.notify(f"Settings for {message.name} (not implemented yet)")


def main(config_path: str = "config.toml") -> None:
    """Run standalone app.

    Args:
        config_path: Path to TOML config file
    """
    app = CmdorcApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
