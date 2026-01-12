"""TUI application for textual-cmdorc.

Direct event handler pattern using FileLinkList + CommandLink.
Flat list of commands in TOML order.

Enhanced with rich tooltips showing:
- Status icon: Run history with results
- Play/Stop button: Trigger conditions and chains
- Command name: Output file preview (last 5 lines)

Multi-config support:
- ConfigSwitcher: Dropdown for switching between named configs
- FileSeparator: Visual separator showing command source files

Architecture:
- CmdorcWidget: Composable widget for embedding in other apps
- CmdorcApp: Standalone app wrapping CmdorcWidget with Header/Footer
"""

import asyncio
import logging
import time
from pathlib import Path

from cmdorc import RunHandle
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Footer, Header, Static
from textual_filelink import CommandLink, FileLinkList, sanitize_id

from cmdorc_frontend.config_discovery import discover_config, resolve_startup_config
from cmdorc_frontend.multiconfig import ConfigSet
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter

from .config_switcher import ConfigSwitcher
from .details_screen import CommandDetailsScreen
from .file_separator import FileSeparator
from .setup_screen import SetupScreen
from .tooltip_builders import TooltipBuilder
from .watcher_status_line import WatcherStatusLine

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


class CmdorcWidget(Widget):
    """Composable widget for cmdorc command orchestration.

    This widget contains all the core orchestration logic and can be embedded
    in other Textual apps (e.g., as part of a 3-column layout).

    Key features:
    - Flat list of commands in TOML order
    - Direct CommandLink usage (no wrappers)
    - Lifecycle callbacks from OrchestratorAdapter
    - Enhanced tooltips for status, triggers, and output

    Usage (Embedded in another app):
        class MyApp(App):
            def compose(self):
                with Horizontal():
                    yield LeftPanel()
                    yield CmdorcWidget("config.toml")
                    yield RightPanel()

    Usage (Standalone - prefer CmdorcApp):
        widget = CmdorcWidget("config.toml")
        # Note: For standalone use, use CmdorcApp instead which adds Header/Footer
    """

    CSS = """
    CmdorcWidget {
        height: 1fr;
        width: 1fr;
    }

    ConfigSwitcher {
        height: 1;
        width: 100%;
        dock: top;
        padding: 0 1;
        border-bottom: solid $accent;
        background: $surface;
        color: $text;
    }

    ConfigSwitcher:hover {
        background: $surface-darken-1;
    }

    WatcherStatusLine {
        height: 1;
        width: 100%;
        dock: top;
        padding: 0 1;
        border-bottom: solid $accent;
        color: $text-muted;
        text-style: bold;
    }

    WatcherStatusLine:hover {
        color: $accent;
        background: $panel;
    }

    FileSeparator {
        height: 1;
        width: 100%;
        color: $text-muted;
        text-style: bold;
        padding: 0 1;
    }

    FileLinkList {
        height: 1fr;
        border: solid $accent;
    }

    CommandLink {
        width: 100%;
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("w", "toggle_watchers", "Toggle file watchers", show=False),
        Binding("ctrl+k", "cycle_config", "Switch config", show=False),
    ]

    def __init__(
        self,
        config_path: str | Path | None = None,
        config_paths: list[str | Path] | None = None,
        config_set: ConfigSet | None = None,
        active_config_name: str | None = None,
        **kwargs,
    ):
        """Initialize widget.

        Args:
            config_path: Path to single TOML config file (backward compatible)
            config_paths: List of TOML config files to merge (multi-config)
            config_set: ConfigSet for named multi-config mode
            active_config_name: Active config name (when using config_set)
        """
        super().__init__(**kwargs)

        # Store multi-config state
        self.config_set = config_set
        self.active_config_name = active_config_name

        # Resolve config paths
        if config_paths is not None:
            self.config_paths = [Path(p) for p in config_paths]
        elif config_path is not None:
            self.config_paths = [Path(config_path)]
        elif config_set and active_config_name:
            named_config = config_set.get_config_by_name(active_config_name)
            if named_config:
                self.config_paths = named_config.get_all_paths()
            else:
                # Fall back to default config
                default = config_set.get_default_config()
                if default:
                    self.config_paths = default.get_all_paths()
                    self.active_config_name = default.name
                else:
                    self.config_paths = []
        elif config_set:
            # Use default config from config_set
            default = config_set.get_default_config()
            if default:
                self.config_paths = default.get_all_paths()
                self.active_config_name = default.name
            else:
                self.config_paths = []
        else:
            # Default to config.toml for backward compatibility
            self.config_paths = [Path("config.toml")]

        # Keep config_path for backward compatibility
        self.config_path = self.config_paths[0] if self.config_paths else Path("config.toml")

        self.adapter: OrchestratorAdapter | None = None
        self.file_list: FileLinkList | None = None
        self.tooltip_builder: TooltipBuilder | None = None
        self.watcher_status: WatcherStatusLine | None = None
        self.config_switcher: ConfigSwitcher | None = None

        # Track running commands for state management
        self.running_commands: set[str] = set()

    def compose(self) -> ComposeResult:
        """Compose widget layout."""
        try:
            # Create adapter (loads config, creates orchestrator)
            if len(self.config_paths) == 1:
                self.adapter = OrchestratorAdapter(config_path=self.config_paths[0])
            else:
                self.adapter = OrchestratorAdapter(config_paths=self.config_paths)

            # Create tooltip builder
            self.tooltip_builder = TooltipBuilder(self.adapter)

            # Build EMPTY command list - items added in on_mount()
            self.file_list = FileLinkList(
                show_toggles=False,
                show_remove=False,
                id="commands-list",
            )

            # Check if watchers are configured
            watcher_count = self.adapter.get_watcher_count()

            # Check if we should show config switcher (multi-config with 2+ configs)
            show_switcher = (
                self.config_set is not None and len(self.config_set.configs) > 1 and self.active_config_name is not None
            )

            with Vertical(id="main-container"):
                # Config switcher (only if multi-config with 2+ configs)
                if show_switcher:
                    self.config_switcher = ConfigSwitcher(
                        config_names=self.config_set.get_config_names(),
                        active_name=self.active_config_name,
                    )
                    yield self.config_switcher

                # Watcher status line (only if watchers configured)
                if watcher_count > 0:
                    self.watcher_status = WatcherStatusLine(
                        watcher_count=watcher_count,
                        enabled=True,  # Start enabled
                        command_template=self.adapter.get_editor_command_template() if self.adapter else None,
                        watcher_configs=self.adapter.get_watcher_configs() if self.adapter else None,
                    )
                    yield self.watcher_status
                else:
                    self.watcher_status = None

                yield self.file_list

        except Exception as e:
            # Fatal config error
            logger.error(f"Failed to initialize widget: {e}")
            yield Static(f"❌ Configuration Error: {e}")

    def _create_command_link(self, cmd_name: str) -> CommandLink:
        """Create a CommandLink widget for the given command.

        Handles status icon mapping from history and error cases.
        Returns CommandLink ready to add to file_list.

        Args:
            cmd_name: Name of the command

        Returns:
            CommandLink widget (either normal or warning version on error)
        """
        try:
            # Get command status from orchestrator
            status = self.adapter.orchestrator.get_status(cmd_name)

            # Extract output path from last run
            initial_output_path = None
            if status and status.last_run and status.last_run.output_file:
                initial_output_path = status.last_run.output_file

            # Extract end_time for timer display (convert to timestamp)
            initial_end_time = None
            if status and status.last_run and status.last_run.end_time:
                initial_end_time = status.last_run.end_time.timestamp()

            # Determine initial status icon based on history
            initial_status_icon = "◯"  # Default to idle
            if status and status.last_run:
                state_name = status.last_run.state.name
                icon_map = {
                    "SUCCESS": "✅",
                    "FAILED": "❌",
                    "CANCELLED": "⚠️",
                }
                initial_status_icon = icon_map.get(state_name, "◯")

            link = CommandLink(
                command_name=cmd_name,
                output_path=initial_output_path,
                end_time=initial_end_time,
                initial_status_icon=initial_status_icon,
                initial_status_tooltip=self.tooltip_builder.build_status_tooltip_idle(cmd_name),
                show_timer=True,
                show_settings=True,
                timer_field_width=8,
                command_template=self.adapter.get_editor_command_template(),
            )
            # Set play/stop button tooltips
            link.set_play_stop_tooltips(
                run_tooltip=self.tooltip_builder.build_play_tooltip(cmd_name),
                stop_tooltip=self.tooltip_builder.build_stop_tooltip(cmd_name, None),
                append_shortcuts=False,
            )
            # Set name/output tooltip
            link.set_name_tooltip(
                self.tooltip_builder.build_output_tooltip(cmd_name, is_running=False),
                append_shortcuts=False,
            )
            return link
        except Exception as e:
            # Config error - return warning link
            logger.error(f"Failed to create link for {cmd_name}: {e}")
            return CommandLink(
                command_name=f"⚠️ {cmd_name}",
                output_path=None,
                initial_status_icon="⚠️",
                initial_status_tooltip=f"Config error: {e}",
                show_settings=False,
                tooltip=f"Error: {e}",
                timer_field_width=8,
                command_template=self.adapter.get_editor_command_template(),
            )

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

                # Track current source file for separators (multi-config only)
                current_source: Path | None = None
                show_separators = len(self.config_paths) > 1

                for cmd_name in cmd_names:
                    # Add file separator if source changed (multi-config mode)
                    if show_separators:
                        cmd_source = self.adapter.get_command_source(cmd_name)
                        if cmd_source and cmd_source != current_source:
                            current_source = cmd_source
                            separator = FileSeparator(cmd_source.name)
                            self.file_list.add_item(separator)
                    # Create and add command link
                    link = self._create_command_link(cmd_name)
                    self.file_list.add_item(link)

            # Wire lifecycle callbacks for all commands
            for cmd_name in self.adapter.get_command_names():
                # Started event (via orchestrator.on_event)
                logger.debug(f"Wiring command_started:{cmd_name} callback")
                self.adapter.orchestrator.on_event(
                    f"command_started:{cmd_name}",
                    lambda h, _ctx, name=cmd_name: self._on_command_started(name, h),
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

            # Start polling for last triggered file (to update watcher status line)
            if self.watcher_status:
                self.set_interval(1.0, self._poll_last_triggered_file)

        except Exception as e:
            logger.error(f"Failed to mount widget: {e}", exc_info=True)

    async def on_unmount(self) -> None:
        """Cleanup on widget removal."""
        if self.adapter:
            self.adapter.detach()

    def _poll_last_triggered_file(self) -> None:
        """Poll adapter for last triggered file and update watcher status line."""
        try:
            if not self.adapter or not self.watcher_status:
                return

            file_path, timestamp = self.adapter.get_last_triggered_file()
            # Only update if we have new info (different from current)
            if (
                file_path
                and timestamp
                and (self.watcher_status.last_file != file_path or self.watcher_status.last_file_time != timestamp)
            ):
                # Use call_later to ensure proper app context for widget updates
                self.call_later(self.watcher_status.set_last_file, file_path, timestamp)
        except Exception:
            # Ignore context errors during app shutdown or transitions
            logger.debug("Context error during lifecycle callback registration (shutdown/transition)")

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
            # Note: We bind on the app, not the widget, so we need to access app
            if hasattr(self, "app") and self.app:
                self.app.bind(
                    key,
                    f"toggle_command('{cmd_name}')",
                    description=f"Run/Stop {cmd_name}",
                    show=False,
                )

    async def toggle_command(self, cmd_name: str) -> None:
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

    async def action_show_details(self) -> None:
        """Show details modal for focused command."""
        try:
            focused = self.app.focused if self.app else None
            if not focused:
                return

            # CommandLink or its children can be focused
            if isinstance(focused, CommandLink):
                cmd_name = focused.command_name
            elif hasattr(focused, "parent") and isinstance(focused.parent, CommandLink):
                cmd_name = focused.parent.command_name
            else:
                return  # No CommandLink focused

            if self.app:
                screen = CommandDetailsScreen(
                    cmd_name=cmd_name,
                    adapter=self.adapter,
                )
                self.app.push_screen(screen)

        except Exception as e:
            logger.error(f"Failed to show details: {e}")

    async def _start_command(self, cmd_name: str) -> None:
        """Start command execution.

        Args:
            cmd_name: Command name
        """
        if not self.adapter:
            return

        logger.info(f"Starting command: {cmd_name}")
        # Note: UI update happens in _on_command_started callback (consolidated path)
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
        """Handle settings icon clicks - show details modal.

        Args:
            event: CommandLink.SettingsClicked message
        """
        logger.debug(f"Settings clicked: {event.name}")
        if self.app:
            screen = CommandDetailsScreen(
                cmd_name=event.name,
                adapter=self.adapter,
            )
            self.app.push_screen(screen)

    def on_watcher_status_line_toggled(self, _event: WatcherStatusLine.Toggled) -> None:
        """Handle click on watcher status line - toggle watchers."""
        if not self.adapter or not self.watcher_status:
            return

        # Toggle watchers based on current state
        if self.adapter.are_watchers_enabled():
            success = self.adapter.disable_watchers()
            if success:
                logger.info("File watchers disabled by user")
                self.watcher_status.set_enabled(False)
        else:
            success = self.adapter.enable_watchers()
            if success:
                logger.info("File watchers enabled by user")
                self.watcher_status.set_enabled(True)

    async def action_toggle_watchers(self) -> None:
        """Toggle file watchers on/off (keyboard shortcut)."""
        if not self.adapter or not self.watcher_status:
            return

        # Simulate click on status line (reuses same logic)
        self.watcher_status.post_message(WatcherStatusLine.Toggled())

    def on_config_switcher_config_selected(self, event: ConfigSwitcher.ConfigSelected) -> None:
        """Handle config switcher selection.

        Args:
            event: ConfigSwitcher.ConfigSelected message
        """
        logger.info(f"Config selected: {event.config_name}")
        asyncio.create_task(self._switch_config(event.config_name))

    async def action_cycle_config(self) -> None:
        """Cycle to next config (keyboard shortcut Ctrl+K)."""
        if self.config_switcher:
            self.config_switcher.cycle_next()

    async def _switch_config(self, config_name: str) -> None:
        """Switch to a different named config.

        Args:
            config_name: Name of the config to switch to
        """
        if not self.config_set:
            logger.warning("Cannot switch config - no ConfigSet available")
            return

        named_config = self.config_set.get_config_by_name(config_name)
        if not named_config:
            logger.error(f"Config not found: {config_name}")
            return

        logger.info(f"Switching to config: {config_name}")

        # Update state
        self.active_config_name = config_name
        self.config_paths = named_config.get_all_paths()
        self.config_path = self.config_paths[0] if self.config_paths else self.config_path

        # Reload with new config
        await self.reload_config()

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
            # Clear output link from previous run (avoid showing stale output)
            link.set_output_path(None)

            # Update output tooltip to reflect no output available yet
            link.set_name_tooltip(
                self.tooltip_builder.build_output_tooltip(name, is_running=True),
                append_shortcuts=False,
            )

            # Update status icon tooltip
            status_tooltip = self.tooltip_builder.build_status_tooltip_running(name, handle)

            # Update stop button tooltip
            stop_tooltip = self.tooltip_builder.build_stop_tooltip(name, handle)

            # Get start_time from handle, or use current time as fallback
            start_time = (
                handle.start_time.timestamp() if handle and handle.start_time else time.time()
            )  # Fallback if handle doesn't have start_time yet

            link.set_status(
                running=True,
                tooltip=status_tooltip,
                stop_tooltip=stop_tooltip,
                start_time=start_time,
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
                end_time=handle.end_time.timestamp() if handle.end_time else None,
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.set_name_tooltip(
                self.tooltip_builder.build_output_tooltip(name, is_running=False),
                append_shortcuts=False,
            )

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
                end_time=handle.end_time.timestamp() if handle.end_time else None,
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.set_name_tooltip(
                self.tooltip_builder.build_output_tooltip(name, is_running=False),
                append_shortcuts=False,
            )

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
                end_time=handle.end_time.timestamp() if handle.end_time else None,
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.set_name_tooltip(
                self.tooltip_builder.build_output_tooltip(name, is_running=False),
                append_shortcuts=False,
            )

            # Update output_path if available
            if handle.output_file:
                link.set_output_path(handle.output_file)

    # ========================================================================
    # Public Methods
    # ========================================================================

    async def reload_config(self) -> None:
        """Reload configuration from disk (rebuilds entire list).

        Returns:
            tuple: (success: bool, message: str)
        """
        logger.info("Reloading configuration...")

        try:
            # Detach old adapter
            if self.adapter:
                self.adapter.detach()

            # Clear running commands state
            self.running_commands.clear()

            # Store old watcher count for comparison
            old_watcher_count = self.watcher_status.watcher_count if self.watcher_status else 0

            # Remove old command list and wait for removal to complete
            if self.file_list:
                await self.file_list.remove()

            # Recreate adapter with new config (single or multi-config)
            if len(self.config_paths) == 1:
                self.adapter = OrchestratorAdapter(config_path=self.config_paths[0])
            else:
                self.adapter = OrchestratorAdapter(config_paths=self.config_paths)

            # Recreate tooltip builder
            self.tooltip_builder = TooltipBuilder(self.adapter)

            # Get new watcher count and update WatcherStatusLine if needed
            new_watcher_count = self.adapter.count_watchers() if self.adapter else 0
            main_container = self.query_one("#main-container", Vertical)

            if old_watcher_count == 0 and new_watcher_count > 0:
                # Watchers were added - create and mount WatcherStatusLine
                self.watcher_status = WatcherStatusLine(
                    watcher_count=new_watcher_count,
                    enabled=True,
                    command_template=self.adapter.get_editor_command_template(),
                    watcher_configs=self.adapter.get_watcher_configs(),
                )
                await main_container.mount(self.watcher_status, before=0)  # Mount at top
            elif old_watcher_count > 0 and new_watcher_count == 0:
                # Watchers were removed - remove WatcherStatusLine
                if self.watcher_status:
                    await self.watcher_status.remove()
                    self.watcher_status = None
            elif old_watcher_count > 0 and new_watcher_count > 0 and old_watcher_count != new_watcher_count:
                # Watcher count changed but both non-zero - update count
                if self.watcher_status:
                    self.watcher_status.watcher_count = new_watcher_count

            # Rebuild EMPTY command list
            self.file_list = FileLinkList(
                show_toggles=False,
                show_remove=False,
                id="commands-list",
            )

            # Mount new list to the main container (not self) to preserve ordering
            await main_container.mount(self.file_list)

            # Track current source file for separators (multi-config only)
            current_source: Path | None = None
            show_separators = len(self.config_paths) > 1

            # THEN populate it (after mounting)
            for cmd_name in self.adapter.get_command_names():
                # Add file separator if source changed (multi-config mode)
                if show_separators:
                    cmd_source = self.adapter.get_command_source(cmd_name)
                    if cmd_source and cmd_source != current_source:
                        current_source = cmd_source
                        separator = FileSeparator(cmd_source.name)
                        self.file_list.add_item(separator)
                # Create and add command link
                link = self._create_command_link(cmd_name)
                self.file_list.add_item(link)

            # Re-attach adapter
            loop = asyncio.get_running_loop()
            self.adapter.attach(loop)

            # Re-wire callbacks
            for cmd_name in self.adapter.get_command_names():
                # Started event (via orchestrator.on_event)
                self.adapter.orchestrator.on_event(
                    f"command_started:{cmd_name}",
                    lambda h, _ctx, name=cmd_name: self._on_command_started(name, h),
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

            logger.info("Configuration reloaded successfully")
            return True, "Configuration reloaded"

        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return False, f"Failed to reload: {e}"

    def get_keyboard_shortcuts(self) -> dict[str, str]:
        """Get keyboard shortcut mapping.

        Returns:
            Dict mapping command_name -> shortcut key
        """
        if self.adapter:
            return self.adapter.get_keyboard_shortcuts()
        return {}

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


class CmdorcApp(App):
    """Standalone TUI application for cmdorc command orchestration.

    This is a thin wrapper around CmdorcWidget that adds:
    - Header and Footer
    - Help screen (h key)
    - Reload config action (r key)
    - Quit action (q key)

    For embedding in other apps, use CmdorcWidget directly instead.

    Usage:
        app = CmdorcApp(config_path="config.toml")
        app.run()
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

    def __init__(
        self,
        config_path: str | Path | None = None,
        config_paths: list[str | Path] | None = None,
        config_set: ConfigSet | None = None,
        active_config_name: str | None = None,
        show_setup: bool = False,
        **kwargs,
    ):
        """Initialize app.

        Args:
            config_path: Path to single TOML config file (backward compatible)
            config_paths: List of TOML config files to merge (multi-config)
            config_set: ConfigSet for named multi-config mode
            active_config_name: Active config name (when using config_set)
            show_setup: Show SetupScreen for first-run experience
        """
        super().__init__(**kwargs)
        self.config_path = config_path
        self.config_paths = config_paths
        self.config_set = config_set
        self.active_config_name = active_config_name
        self.show_setup = show_setup
        self.cmdorc_widget: CmdorcWidget | None = None

    def compose(self) -> ComposeResult:
        """Compose app layout."""
        yield Header()

        if self.show_setup:
            # Don't create widget yet - will mount after setup
            yield Static("Welcome! Starting setup...", id="setup-placeholder")
        else:
            try:
                # Create and yield the widget (normal path)
                self.cmdorc_widget = CmdorcWidget(
                    config_path=self.config_path,
                    config_paths=self.config_paths,
                    config_set=self.config_set,
                    active_config_name=self.active_config_name,
                )
                yield self.cmdorc_widget

            except Exception as e:
                # Fatal config error
                logger.error(f"Failed to initialize app: {e}")
                yield Static(f"❌ Configuration Error: {e}")

        yield Footer()

    async def on_mount(self) -> None:
        """Handle mount - show setup screen if needed."""
        if self.show_setup:
            # Use push_screen with callback instead of push_screen_wait
            # to avoid NoActiveWorker error
            self.push_screen(SetupScreen(), callback=self._handle_setup_result)

    def _handle_setup_result(self, result: str | None) -> None:
        """Handle SetupScreen dismissal result.

        Args:
            result: Path to created config file, or None if user exited
        """
        if result is None:
            # User chose exit - close app immediately
            self.exit()
            return

        # Config was created - initialize widget with discovered config
        asyncio.create_task(self._initialize_with_config())

    async def _initialize_with_config(self) -> None:
        """Initialize CmdorcWidget after config is created by SetupScreen."""
        try:
            # Remove placeholder
            placeholder = self.query_one("#setup-placeholder", Static)
            await placeholder.remove()

            # Re-discover config (should find what SetupScreen created)
            discovery = discover_config()

            if discovery.mode == "none":
                # This shouldn't happen - SetupScreen just created a config
                await self.mount(Static("❌ Error: No config found after setup"))
                return

            # Resolve startup config
            config_set, active_name, config_paths = resolve_startup_config(discovery)

            # Create and mount widget with discovered config
            self.cmdorc_widget = CmdorcWidget(
                config_paths=config_paths,
                config_set=config_set,
                active_config_name=active_name,
            )

            # Mount before Footer
            await self.mount(self.cmdorc_widget, before=self.query_one(Footer))

        except Exception as e:
            logger.error(f"Failed to initialize after setup: {e}")
            await self.mount(Static(f"❌ Error initializing: {e}"))

    async def action_toggle_command(self, cmd_name: str) -> None:
        """Toggle command execution (delegated to widget).

        Args:
            cmd_name: Command name to toggle
        """
        if self.cmdorc_widget:
            await self.cmdorc_widget.toggle_command(cmd_name)

    async def action_reload_config(self) -> None:
        """Reload configuration from disk (delegated to widget)."""
        if not self.cmdorc_widget:
            self.notify("Widget not initialized", severity="warning")
            return

        # Notify user that reload has started
        self.notify("Reloading configuration...", severity="information")

        success, message = await self.cmdorc_widget.reload_config()
        if success:
            self.notify(message, severity="information")
        else:
            self.notify(message, severity="error")

    def action_show_help(self) -> None:
        """Show help screen with keyboard shortcuts."""
        if not self.cmdorc_widget:
            self.notify("Widget not initialized", severity="warning")
            return

        shortcuts = self.cmdorc_widget.get_keyboard_shortcuts()
        self.push_screen(HelpScreen(shortcuts))

    async def action_quit(self) -> None:
        """Quit application."""
        self.exit()


def main(config_path: str = "config.toml") -> None:
    """Run standalone app.

    Args:
        config_path: Path to TOML config file
    """
    app = CmdorcApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
