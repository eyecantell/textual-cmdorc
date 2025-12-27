"""TUI application for textual-cmdorc.

Direct event handler pattern using FileLinkList + CommandLink.
Flat list of commands in TOML order.

Enhanced with rich tooltips showing:
- Status icon: Run history with results
- Play/Stop button: Trigger conditions and chains
- Command name: Output file preview (last 5 lines)
"""

import asyncio
import logging
from pathlib import Path

from cmdorc import RunHandle
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static
from textual_filelink import CommandLink, FileLinkList, sanitize_id

from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter

from .tooltip_builders import TooltipBuilder

# Logger for warnings and errors
logger = logging.getLogger(__name__)


class HelpScreen(ModalScreen):
    """Modal help screen showing keyboard shortcuts."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, shortcuts: dict[str, str], **kwargs):
        """Initialize help screen.

        Args:
            shortcuts: Dict mapping command_name -> key
        """
        super().__init__(**kwargs)
        self.shortcuts = shortcuts

    def compose(self) -> ComposeResult:
        """Compose help content."""
        with Vertical():
            yield Static("# Keyboard Shortcuts", classes="help-header")
            yield Static("")

            # Command shortcuts
            if self.shortcuts:
                yield Static("## Command Shortcuts")
                for cmd_name, key in sorted(self.shortcuts.items()):
                    yield Static(f"  [{key}] - Run/Stop {cmd_name}")
                yield Static("")

            # App shortcuts
            yield Static("## App Shortcuts")
            yield Static("  [h] - Show this help")
            yield Static("  [r] - Reload configuration")
            yield Static("  [q] - Quit application")
            yield Static("")
            yield Static("Press ESC to close", classes="help-footer")


class CmdorcApp(App):
    """TUI application for cmdorc command orchestration.

    Key features:
    - Flat list of commands in TOML order
    - Direct CommandLink usage (no wrappers)
    - Lifecycle callbacks from OrchestratorAdapter
    - Enhanced tooltips:
      - Status icon: Run history and results
      - Play/Stop: Trigger conditions and chains
      - Command name: Output preview (last 5 lines)
    """

    TITLE = "cmdorc"
    BINDINGS = [
        Binding("h", "show_help", "Help"),
        Binding("r", "reload_config", "Reload"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    FileLinkList {
        height: 1fr;
        border: solid $accent;
    }

    CommandLink {
        width: 100%;
        margin: 0 0 1 0;
    }

    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 60;
        height: auto;
        background: $panel;
        border: solid $accent;
        padding: 2;
    }

    .help-header {
        text-style: bold;
        color: $accent;
    }

    .help-footer {
        text-style: italic;
        color: $text-muted;
    }
    """

    def __init__(self, config_path: str = "config.toml", **kwargs):
        """Initialize app.

        Args:
            config_path: Path to TOML config file
        """
        super().__init__(**kwargs)
        self.config_path = Path(config_path)
        self.adapter: OrchestratorAdapter | None = None
        self.file_list: FileLinkList | None = None
        self.tooltip_builder: TooltipBuilder | None = None

        # Track running commands for state management
        self.running_commands: set[str] = set()

    def compose(self) -> ComposeResult:
        """Compose app layout."""
        yield Header()

        try:
            # Create adapter (loads config, creates orchestrator)
            self.adapter = OrchestratorAdapter(self.config_path)

            # Create tooltip builder
            self.tooltip_builder = TooltipBuilder(self.adapter)

            # Build EMPTY command list - items added in on_mount()
            self.file_list = FileLinkList(
                show_toggles=False,
                show_remove=False,
                id="commands-list",
            )

            yield self.file_list

        except Exception as e:
            # Fatal config error
            logger.error(f"Failed to initialize app: {e}")
            yield Static(f"❌ Configuration Error: {e}")

        yield Footer()

    async def on_mount(self) -> None:
        """Attach adapter to event loop, populate list, and wire callbacks."""
        if not self.adapter:
            logger.error("Adapter not initialized")
            return

        try:
            # Attach to event loop
            loop = asyncio.get_running_loop()
            self.adapter.attach(loop)

            # Populate the list (after it's mounted)
            if self.file_list is not None:
                cmd_names = self.adapter.get_command_names()

                for cmd_name in cmd_names:
                    try:
                        # Check if there's a historical run with output file
                        status = self.adapter.orchestrator.get_status(cmd_name)
                        initial_output_path = None
                        if status and status.last_run and status.last_run.output_file:
                            initial_output_path = status.last_run.output_file

                        link = CommandLink(
                            command_name=cmd_name,
                            output_path=initial_output_path,
                            initial_status_icon="◯",
                            initial_status_tooltip=self.tooltip_builder.build_status_tooltip_idle(cmd_name),
                            show_settings=True,
                            tooltip=self.tooltip_builder.build_output_tooltip(cmd_name),
                        )
                        # Set play/stop button tooltips
                        link.set_play_stop_tooltips(
                            run_tooltip=self.tooltip_builder.build_play_tooltip(cmd_name),
                            stop_tooltip=self.tooltip_builder.build_stop_tooltip(cmd_name, None),
                            append_shortcuts=False,
                        )
                        self.file_list.add_item(link)
                    except Exception as e:
                        # Config error - show warning icon
                        logger.error(f"Failed to create link for {cmd_name}: {e}")
                        link = CommandLink(
                            command_name=f"⚠️ {cmd_name}",
                            output_path=None,
                            initial_status_icon="⚠️",
                            initial_status_tooltip=f"Config error: {e}",
                            show_settings=False,
                            tooltip=f"Error: {e}",
                        )
                        self.file_list.add_item(link)

            # Wire lifecycle callbacks for all commands
            for cmd_name in self.adapter.get_command_names():
                # Started event (via orchestrator.on_event)
                logger.debug(f"Wiring command_started:{cmd_name} callback")
                self.adapter.orchestrator.on_event(
                    f"command_started:{cmd_name}",
                    lambda h, ctx, name=cmd_name: self._on_command_started(name, h),
                )
                # Completion events (via adapter lifecycle callbacks)
                self.adapter.on_command_success(
                    cmd_name,
                    lambda h, name=cmd_name: self._on_command_success(name, h),
                )
                self.adapter.on_command_failed(
                    cmd_name,
                    lambda h, name=cmd_name: self._on_command_failed(name, h),
                )
                self.adapter.on_command_cancelled(
                    cmd_name,
                    lambda h, name=cmd_name: self._on_command_cancelled(name, h),
                )

            # Bind global keyboard shortcuts
            self._bind_keyboard_shortcuts()

        except Exception as e:
            logger.error(f"Failed to mount app: {e}", exc_info=True)
            self.exit(message=f"Error: {e}")

    async def on_unmount(self) -> None:
        """Cleanup on exit."""
        if self.adapter:
            self.adapter.detach()

    def _bind_keyboard_shortcuts(self) -> None:
        """Bind global keyboard shortcuts from config."""
        if not self.adapter or not self.adapter.keyboard_config.enabled:
            return

        shortcuts = self.adapter.keyboard_config.shortcuts
        for cmd_name, key in shortcuts.items():
            # Validate key is alphanumeric or f-key
            if not (key.isalnum() or key.startswith("f")):
                logger.warning(f"Invalid keyboard shortcut: {key} for {cmd_name}")
                continue

            # Bind key to toggle command (play if idle, stop if running)
            self.bind(
                key,
                f"toggle_command('{cmd_name}')",
                description=f"Run/Stop {cmd_name}",
                show=False,
            )

    async def action_toggle_command(self, cmd_name: str) -> None:
        """Toggle command execution (play if idle, stop if running).

        Args:
            cmd_name: Command name to toggle
        """
        if cmd_name in self.running_commands:
            # Stop running command
            await self._stop_command(cmd_name)
        else:
            # Start idle command
            await self._start_command(cmd_name)

    async def _start_command(self, cmd_name: str) -> None:
        """Start command execution.

        Args:
            cmd_name: Command name
        """
        if not self.adapter:
            return

        logger.info(f"Starting command: {cmd_name}")
        self.running_commands.add(cmd_name)

        # Update UI to running state (generic tooltip until handle available)
        link = self._get_link(cmd_name)
        if link:
            link.set_status(
                running=True,
                icon="⏳",
                tooltip=f"Starting {cmd_name}...",
            )

        # Request execution (async, returns immediately)
        self.adapter.request_run(cmd_name)

    async def _stop_command(self, cmd_name: str) -> None:
        """Stop command execution.

        Args:
            cmd_name: Command name
        """
        if not self.adapter:
            return

        logger.info(f"Stopping command: {cmd_name}")
        self.running_commands.discard(cmd_name)

        # Update UI to stopped state
        link = self._get_link(cmd_name)
        if link:
            link.set_status(
                running=False,
                icon="⚠️",
                tooltip="Stopped",
            )

        # Request cancellation
        self.adapter.request_cancel(cmd_name)

    # ========================================================================
    # CommandLink Message Handlers
    # ========================================================================

    def on_command_link_play_clicked(self, event: CommandLink.PlayClicked) -> None:
        """Handle play button clicks.

        Args:
            event: CommandLink.PlayClicked message
        """
        logger.debug(f"Play clicked: {event.name}")
        asyncio.create_task(self._start_command(event.name))

    def on_command_link_stop_clicked(self, event: CommandLink.StopClicked) -> None:
        """Handle stop button clicks.

        Args:
            event: CommandLink.StopClicked message
        """
        logger.debug(f"Stop clicked: {event.name}")
        asyncio.create_task(self._stop_command(event.name))

    def on_command_link_settings_clicked(self, event: CommandLink.SettingsClicked) -> None:
        """Handle settings icon clicks (placeholder).

        Args:
            event: CommandLink.SettingsClicked message
        """
        logger.debug(f"Settings clicked: {event.name}")
        self.notify(f"Settings for {event.name} (coming soon)")

    # ========================================================================
    # Lifecycle Callbacks (from OrchestratorAdapter)
    # ========================================================================

    def _on_command_started(self, name: str, handle: RunHandle | None) -> None:
        """Handle command started event.

        Args:
            name: Command name
            handle: RunHandle for the started run (may be None for command_started events)
        """
        logger.debug(f"_on_command_started called for {name}, handle={handle}")

        logger.info(f"Command started: {name}")
        self.running_commands.add(name)

        link = self._get_link(name)
        if link:
            # Update status icon tooltip
            status_tooltip = self.tooltip_builder.build_status_tooltip_running(name, handle)

            # Update stop button tooltip
            stop_tooltip = self.tooltip_builder.build_stop_tooltip(name, handle)

            link.set_status(
                running=True,
                icon="⏳",
                tooltip=status_tooltip,
                stop_tooltip=stop_tooltip,
                append_shortcuts=False,
            )

    def _on_command_success(self, name: str, handle: RunHandle) -> None:
        """Handle successful command completion.

        Args:
            name: Command name
            handle: RunHandle with result
        """
        logger.info(f"Command succeeded: {name}")
        self.running_commands.discard(name)

        link = self._get_link(name)
        if link:
            # Update tooltips
            link.set_status(
                running=False,
                icon="✅",
                tooltip=self.tooltip_builder.build_status_tooltip_completed(name, handle),
                run_tooltip=self.tooltip_builder.build_play_tooltip(name),
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.tooltip = self.tooltip_builder.build_output_tooltip(name)

            # Update output_path if available
            if handle.output_file:
                link.set_output_path(handle.output_file)

    def _on_command_failed(self, name: str, handle: RunHandle) -> None:
        """Handle failed command.

        Args:
            name: Command name
            handle: RunHandle with result
        """
        logger.error(f"Command failed: {name}")
        self.running_commands.discard(name)

        link = self._get_link(name)
        if link:
            # Update tooltips
            link.set_status(
                running=False,
                icon="❌",
                tooltip=self.tooltip_builder.build_status_tooltip_completed(name, handle),
                run_tooltip=self.tooltip_builder.build_play_tooltip(name),
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.tooltip = self.tooltip_builder.build_output_tooltip(name)

            # Update output_path if available
            if handle.output_file:
                link.set_output_path(handle.output_file)

    def _on_command_cancelled(self, name: str, handle: RunHandle) -> None:
        """Handle cancelled command.

        Args:
            name: Command name
            handle: RunHandle with result
        """
        logger.info(f"Command cancelled: {name}")
        self.running_commands.discard(name)

        link = self._get_link(name)
        if link:
            # Update tooltips
            link.set_status(
                running=False,
                icon="⚠️",
                tooltip=self.tooltip_builder.build_status_tooltip_completed(name, handle),
                run_tooltip=self.tooltip_builder.build_play_tooltip(name),
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.tooltip = self.tooltip_builder.build_output_tooltip(name)

            # Update output_path if available
            if handle.output_file:
                link.set_output_path(handle.output_file)

    # ========================================================================
    # App Actions
    # ========================================================================

    async def action_reload_config(self) -> None:
        """Reload configuration from disk (rebuilds entire list)."""
        logger.info("Reloading configuration...")

        try:
            # Detach old adapter
            if self.adapter:
                self.adapter.detach()

            # Clear running commands state
            self.running_commands.clear()

            # Remove old command list and wait for removal to complete
            if self.file_list:
                await self.file_list.remove()

            # Recreate adapter with new config
            self.adapter = OrchestratorAdapter(self.config_path)

            # Recreate tooltip builder
            self.tooltip_builder = TooltipBuilder(self.adapter)

            # Rebuild EMPTY command list
            self.file_list = FileLinkList(
                show_toggles=False,
                show_remove=False,
                id="commands-list",
            )

            # Mount new list FIRST
            await self.mount(self.file_list, before=self.query_one(Footer))

            # THEN populate it (after mounting)
            for cmd_name in self.adapter.get_command_names():
                try:
                    # Check if there's a historical run with output file
                    status = self.adapter.orchestrator.get_status(cmd_name)
                    initial_output_path = None
                    if status and status.last_run and status.last_run.output_file:
                        initial_output_path = status.last_run.output_file

                    link = CommandLink(
                        command_name=cmd_name,
                        output_path=initial_output_path,
                        initial_status_icon="◯",
                        initial_status_tooltip=self.tooltip_builder.build_status_tooltip_idle(cmd_name),
                        show_settings=True,
                        tooltip=self.tooltip_builder.build_output_tooltip(cmd_name),
                    )
                    link.set_play_stop_tooltips(
                        run_tooltip=self.tooltip_builder.build_play_tooltip(cmd_name),
                        stop_tooltip=self.tooltip_builder.build_stop_tooltip(cmd_name, None),
                        append_shortcuts=False,
                    )
                    self.file_list.add_item(link)
                except Exception as e:
                    logger.error(f"Failed to create link for {cmd_name}: {e}")
                    link = CommandLink(
                        command_name=cmd_name,
                        output_path=None,
                        initial_status_icon="⚠️",
                        initial_status_tooltip=f"Config error: {e}",
                        show_settings=False,
                        tooltip=f"Error: {e}",
                    )
                    self.file_list.add_item(link)

            # Re-attach adapter
            loop = asyncio.get_running_loop()
            self.adapter.attach(loop)

            # Re-wire callbacks
            for cmd_name in self.adapter.get_command_names():
                # Started event (via orchestrator.on_event)
                self.adapter.orchestrator.on_event(
                    f"command_started:{cmd_name}",
                    lambda h, ctx, name=cmd_name: self._on_command_started(name, h),
                )
                # Completion events (via adapter lifecycle callbacks)
                self.adapter.on_command_success(
                    cmd_name,
                    lambda h, name=cmd_name: self._on_command_success(name, h),
                )
                self.adapter.on_command_failed(
                    cmd_name,
                    lambda h, name=cmd_name: self._on_command_failed(name, h),
                )
                self.adapter.on_command_cancelled(
                    cmd_name,
                    lambda h, name=cmd_name: self._on_command_cancelled(name, h),
                )

            # Re-bind keyboard shortcuts
            self._bind_keyboard_shortcuts()

            self.notify("Configuration reloaded", severity="information")
            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            self.notify(f"Failed to reload: {e}", severity="error")

    def action_show_help(self) -> None:
        """Show help screen with keyboard shortcuts."""
        if not self.adapter:
            self.notify("Adapter not initialized", severity="warning")
            return

        shortcuts = self.adapter.keyboard_config.shortcuts
        self.push_screen(HelpScreen(shortcuts))

    async def action_quit(self) -> None:
        """Quit application."""
        self.exit()

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_link(self, cmd_name: str) -> CommandLink | None:
        """Get CommandLink widget by command name.

        Args:
            cmd_name: Command name

        Returns:
            CommandLink widget or None if not found
        """
        try:
            link_id = sanitize_id(cmd_name)
            return self.query_one(f"#{link_id}", CommandLink)
        except Exception as e:
            logger.warning(f"Failed to get link for {cmd_name}: {e}")
            return None


def main(config_path: str = "config.toml") -> None:
    """Run standalone app.

    Args:
        config_path: Path to TOML config file
    """
    app = CmdorcApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
