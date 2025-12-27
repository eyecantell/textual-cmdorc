"""Simplified TUI application for textual-cmdorc.

Direct event handler pattern using FileLinkList + CommandLink.
No complex architecture - just flat list of commands in TOML order.

Enhanced with rich tooltips showing:
- Status icon: Run history with results
- Play/Stop button: Trigger conditions and chains
- Command name: Output file preview (last 5 lines)
"""

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path

from cmdorc import RunHandle
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static
from textual_filelink import CommandLink, FileLinkList, sanitize_id

from cmdorc_frontend.models import TriggerSource
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter

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


class SimpleApp(App):
    """Simplified TUI shell using direct event handlers.

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

        # Track running commands for state management
        self.running_commands: set[str] = set()

    def compose(self) -> ComposeResult:
        """Compose app layout."""
        yield Header()

        try:
            # Create adapter (loads config, creates orchestrator)
            self.adapter = OrchestratorAdapter(self.config_path)

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
                            initial_status_tooltip=self._build_status_tooltip_idle(cmd_name),
                            show_settings=True,
                            tooltip=self._build_output_tooltip(cmd_name),
                        )
                        # Set play/stop button tooltips
                        link.set_play_stop_tooltips(
                            run_tooltip=self._build_play_tooltip(cmd_name),
                            stop_tooltip=self._build_stop_tooltip(cmd_name, None),
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
            status_tooltip = self._build_status_tooltip_running(name, handle)

            # Update stop button tooltip
            stop_tooltip = self._build_stop_tooltip(name, handle)

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
                tooltip=self._build_status_tooltip_completed(name, handle),
                run_tooltip=self._build_play_tooltip(name),
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.tooltip = self._build_output_tooltip(name)

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
                tooltip=self._build_status_tooltip_completed(name, handle),
                run_tooltip=self._build_play_tooltip(name),
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.tooltip = self._build_output_tooltip(name)

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
                tooltip=self._build_status_tooltip_completed(name, handle),
                run_tooltip=self._build_play_tooltip(name),
                append_shortcuts=False,
            )

            # Update command name tooltip with output preview
            link.tooltip = self._build_output_tooltip(name)

            # Update output_path if available
            if handle.output_file:
                link.set_output_path(handle.output_file)

    # ========================================================================
    # Status Icon Tooltip Builders (Run History)
    # ========================================================================

    def _build_status_tooltip_idle(self, cmd_name: str) -> str:
        """Build tooltip for idle command status icon.

        Shows:
        - History if available (loaded from disk)
        - "Not yet run" if no history

        Args:
            cmd_name: Command name

        Returns:
            Formatted tooltip string
        """
        if not self.adapter:
            return "◯ Not yet run"

        try:
            lines = [cmd_name, "─" * len(cmd_name)]

            # Check for historical runs loaded from disk
            history = self.adapter.orchestrator.get_history(cmd_name, limit=3)

            if history and len(history) > 0:
                # Show historical runs
                if len(history) > 1:
                    lines.append("Last 3 runs:")
                else:
                    lines.append("Last run:")

                for result in history:
                    # Status icon
                    icon = {"SUCCESS": "✅", "FAILED": "❌", "CANCELLED": "⚠️"}.get(result.state.name, "◯")

                    # Time ago
                    ago = self._format_time_ago(result.end_time) if result.end_time else "?"

                    # Duration
                    duration = result.duration_str or "?"

                    lines.append(f"  {icon} {ago} for {duration}")

                lines.append("")

                # Resolved command
                command_str = self._get_command_string(cmd_name)
                lines.append(f"Command: {command_str}")
            else:
                # No history available
                lines.append("◯ Not yet run")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to build idle status tooltip for {cmd_name}: {e}")
            return "◯ Not yet run"

    def _build_status_tooltip_running(self, cmd_name: str, handle: RunHandle | None) -> str:
        """Build tooltip for running command status icon.

        Shows:
        - Elapsed time
        - Resolved command

        Args:
            cmd_name: Command name
            handle: RunHandle with timing info

        Returns:
            Formatted tooltip string
        """
        if not self.adapter:
            return "Running..."

        try:
            lines = [cmd_name, "─" * len(cmd_name)]

            # Elapsed time
            if handle and handle.start_time:
                elapsed = self._format_elapsed_time(handle.start_time)
                lines.append(f"⏳ Running for {elapsed}")
            else:
                lines.append("⏳ Running...")

            lines.append("")

            # Resolved command
            command_str = self._get_command_string(cmd_name)
            lines.append(f"Command: {command_str}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build running status tooltip for {cmd_name}: {e}")
            return "Running..."

    def _build_status_tooltip_completed(self, cmd_name: str, handle: RunHandle) -> str:
        """Build tooltip for completed command status icon.

        Shows:
        - Last 3 runs with status, time ago, duration, exit code
        - Resolved command

        Args:
            cmd_name: Command name
            handle: RunHandle with result

        Returns:
            Formatted tooltip string
        """
        if not self.adapter:
            return "Completed"

        try:
            lines = [cmd_name, "─" * len(cmd_name)]

            # Try to get history (last 3 runs)
            history = self.adapter.orchestrator.get_history(cmd_name, limit=3)

            if history and len(history) > 1:
                # Show last 3 runs
                lines.append("Last 3 runs:")
                for result in history:
                    # Status icon
                    icon = {"SUCCESS": "✅", "FAILED": "❌", "CANCELLED": "⚠️"}.get(result.state.name, "◯")

                    # Time ago
                    ago = self._format_time_ago(result.end_time) if result.end_time else "?"

                    # Duration
                    duration = result.duration_str or "?"

                    lines.append(f"  {icon} {ago} for {duration}")
            else:
                # Single run info
                icon = {"SUCCESS": "✅", "FAILED": "❌", "CANCELLED": "⚠️"}.get(handle.state.name, "◯")
                ago = self._format_time_ago(handle.end_time) if handle.end_time else "?"
                duration = handle.duration_str or "?"

                lines.append("Last run:")
                lines.append(f"  {icon} {ago} for {duration}")

            lines.append("")

            # Resolved command
            command_str = self._get_command_string(cmd_name)
            lines.append(f"Command: {command_str}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build completed status tooltip for {cmd_name}: {e}")
            return "Completed"

    # ========================================================================
    # Play/Stop Button Tooltip Builders (Trigger Conditions)
    # ========================================================================

    def _build_play_tooltip(self, cmd_name: str) -> str:
        """Build tooltip for play button.

        Shows:
        - Resolved command
        - Trigger sources
        - Downstream commands (success/failure)
        - Cancel triggers
        - Keyboard shortcut

        Args:
            cmd_name: Command name

        Returns:
            Formatted tooltip string
        """
        if not self.adapter:
            return "Run command"

        try:
            lines = [f"▶️ Run {cmd_name}", ""]

            # Resolved command
            command_str = self._get_command_string(cmd_name)
            lines.append(f"Command: {command_str}")
            lines.append("")

            # Get command config
            config = self.adapter.orchestrator._runtime.get_command(cmd_name)
            if not config:
                return "\n".join(lines)

            # Triggers
            lines.append("Triggers:")
            if config.triggers:
                for trigger in config.triggers:
                    # Format trigger semantically
                    if trigger.startswith("command_success:"):
                        trigger_cmd = trigger.split(":", 1)[1]
                        lines.append(f"  • After {trigger_cmd} succeeds")
                    elif trigger.startswith("command_failed:"):
                        trigger_cmd = trigger.split(":", 1)[1]
                        lines.append(f"  • After {trigger_cmd} fails")
                    else:
                        lines.append(f"  • {trigger}")

            # Manual trigger
            shortcut = self.adapter.keyboard_config.shortcuts.get(cmd_name)
            if shortcut:
                lines.append(f"  • [{shortcut}] manual")
            else:
                lines.append("  • manual")

            # Downstream on success
            downstream_success = self._get_downstream_commands(cmd_name, "success")
            if downstream_success:
                lines.append("")
                lines.append("On success →")
                for next_cmd in downstream_success[:3]:
                    lines.append(f"  → {next_cmd}")
                if len(downstream_success) > 3:
                    lines.append(f"  ... and {len(downstream_success) - 3} more")

            # Downstream on failure
            downstream_failure = self._get_downstream_commands(cmd_name, "failed")
            if downstream_failure:
                lines.append("")
                lines.append("On failure →")
                for next_cmd in downstream_failure[:3]:
                    lines.append(f"  → {next_cmd}")
                if len(downstream_failure) > 3:
                    lines.append(f"  ... and {len(downstream_failure) - 3} more")

            # Cancel triggers
            if config.cancel_on_triggers:
                lines.append("")
                lines.append("Cancel on:")
                for trigger in config.cancel_on_triggers[:3]:
                    lines.append(f"  • {trigger}")
                if len(config.cancel_on_triggers) > 3:
                    lines.append(f"  ... and {len(config.cancel_on_triggers) - 3} more")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build play tooltip for {cmd_name}: {e}")
            return "Run command"

    def _build_stop_tooltip(self, cmd_name: str, handle: RunHandle | None) -> str:
        """Build tooltip for stop button.

        Shows:
        - Elapsed time
        - Resolved command
        - Semantic trigger summary
        - Full trigger chain
        - Keyboard shortcut

        Args:
            cmd_name: Command name
            handle: RunHandle with trigger chain (may be None)

        Returns:
            Formatted tooltip string
        """
        if not self.adapter:
            return "Stop command"

        try:
            lines = [f"⏹️ Stop {cmd_name}", ""]

            # Elapsed time
            if handle and handle.start_time:
                elapsed = self._format_elapsed_time(handle.start_time)
                lines.append(f"Running for {elapsed}")
                lines.append("")

            # Resolved command
            if handle and handle.resolved_command:
                lines.append(f"Command: {handle.resolved_command.command}")
            else:
                command_str = self._get_command_string(cmd_name)
                lines.append(f"Command: {command_str}")
            lines.append("")

            # Trigger summary and chain
            if handle and handle.trigger_chain:
                trigger_source = TriggerSource.from_trigger_chain(handle.trigger_chain)
                semantic = trigger_source.get_semantic_summary()
                lines.append(f"Trigger: {semantic}")

                # Show full chain if multiple hops
                if len(handle.trigger_chain) > 1:
                    lines.append("")
                    lines.append("Chain:")
                    chain = trigger_source.format_chain(max_width=50)
                    lines.append(f"  {chain}")

            # Keyboard shortcut
            shortcut = self.adapter.keyboard_config.shortcuts.get(cmd_name)
            if shortcut:
                lines.append("")
                lines.append(f"[{shortcut}] to stop")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build stop tooltip for {cmd_name}: {e}")
            return "Stop command"

    # ========================================================================
    # Command Name Tooltip Builder (Output Preview)
    # ========================================================================

    def _build_output_tooltip(self, cmd_name: str) -> str:
        """Build tooltip for command name (output preview).

        Shows:
        - Output file path
        - Last 5 lines of output (always, even if file > 5 lines)
        - Click hint

        Args:
            cmd_name: Command name

        Returns:
            Formatted tooltip string
        """
        if not self.adapter:
            return cmd_name

        try:
            lines = [cmd_name, ""]

            # Get output file and preview
            preview_data = self._get_output_preview(cmd_name)

            if not preview_data:
                lines.append("No output available yet")
                return "\n".join(lines)

            output_path, preview_lines, total_lines = preview_data

            # Show file path
            lines.append(f"Open: {output_path}")
            lines.append("")

            # Show preview (last 5 lines)
            if preview_lines:
                lines.append("Last 5 lines:")
                lines.append("─" * 40)
                lines.extend(preview_lines)
                lines.append("─" * 40)
            else:
                lines.append("(empty output)")
                lines.append("─" * 40)

            lines.append("")

            # Show total line count if > 5
            if total_lines > 5:
                lines.append(f"[{total_lines} total lines]")

            lines.append("Click to open in editor")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build output tooltip for {cmd_name}: {e}")
            return cmd_name

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
                        initial_status_tooltip=self._build_status_tooltip_idle(cmd_name),
                        show_settings=True,
                        tooltip=self._build_output_tooltip(cmd_name),
                    )
                    link.set_play_stop_tooltips(
                        run_tooltip=self._build_play_tooltip(cmd_name),
                        stop_tooltip=self._build_stop_tooltip(cmd_name, None),
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

    def _get_command_string(self, cmd_name: str) -> str:
        """Get resolved command string for a command using preview_command().

        Args:
            cmd_name: Command name

        Returns:
            Resolved command string or error message
        """
        if not self.adapter:
            return "No adapter"

        try:
            preview = self.adapter.orchestrator.preview_command(cmd_name)
            return preview.command
        except Exception as e:
            logger.error(f"Failed to get command string for {cmd_name}: {e}")
            return f"Error: {e}"

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

    def _get_downstream_commands(self, cmd_name: str, trigger_type: str = "success") -> list[str]:
        """Get commands triggered after success/failure.

        Args:
            cmd_name: Command name
            trigger_type: "success" or "failed"

        Returns:
            List of downstream command names
        """
        if not self.adapter:
            return []

        try:
            trigger_graph = self.adapter.orchestrator.get_trigger_graph()
            trigger_key = f"command_{trigger_type}:{cmd_name}"
            return trigger_graph.get(trigger_key, [])
        except Exception as e:
            logger.error(f"Failed to get downstream for {cmd_name}: {e}")
            return []

    def _get_output_preview(self, cmd_name: str) -> tuple[str, list[str], int] | None:
        """Get output file path and preview (last 5 lines).

        Args:
            cmd_name: Command name

        Returns:
            (file_path, preview_lines, total_lines) if output available, else None
        """
        if not self.adapter:
            return None

        try:
            # Get latest result
            status = self.adapter.orchestrator.get_status(cmd_name)
            if not status or not status.last_run or not status.last_run.output_file:
                return None

            output_file = status.last_run.output_file

            # Read output file
            try:
                with open(output_file) as f:
                    lines = f.readlines()

                total_lines = len(lines)

                # Get last 5 lines (or all if fewer)
                preview = lines[-5:] if len(lines) > 5 else lines

                # Strip ANSI codes and clean up
                preview = [self._strip_ansi(line.rstrip()) for line in preview]

                # Truncate long lines to 60 chars
                preview = [line[:60] + "..." if len(line) > 60 else line for line in preview]

                return (str(output_file), preview, total_lines)

            except Exception as e:
                logger.error(f"Failed to read output file {output_file}: {e}")
                return None

        except Exception as e:
            logger.error(f"Failed to get output preview for {cmd_name}: {e}")
            return None

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text.

        Args:
            text: Text potentially containing ANSI codes

        Returns:
            Text with ANSI codes removed
        """
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    def _format_time_ago(self, timestamp: datetime | float | None) -> str:
        """Format relative timestamp.

        Args:
            timestamp: datetime object or Unix timestamp

        Returns:
            Human-readable relative time (e.g., "2s ago", "5m ago")
        """
        if not timestamp:
            return "?"

        try:
            # Handle both datetime and float timestamps
            if isinstance(timestamp, datetime):
                delta = datetime.now() - timestamp
            else:
                delta = datetime.now() - datetime.fromtimestamp(timestamp)

            seconds = delta.total_seconds()

            if seconds < 1:
                return "just now"
            elif seconds < 60:
                return f"{int(seconds)}s ago"
            elif seconds < 3600:
                return f"{int(seconds // 60)}m ago"
            elif seconds < 86400:
                return f"{int(seconds // 3600)}h ago"
            else:
                return f"{int(seconds // 86400)}d ago"

        except Exception as e:
            logger.error(f"Failed to format time ago: {e}")
            return "?"

    def _format_elapsed_time(self, start_time: float) -> str:
        """Format elapsed time from start timestamp.

        Args:
            start_time: Unix timestamp of start time

        Returns:
            Human-readable elapsed time (e.g., "2s", "5m 30s", "1h 5m")
        """
        try:
            elapsed = datetime.now().timestamp() - start_time

            if elapsed < 60:
                return f"{int(elapsed)}s"
            elif elapsed < 3600:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                return f"{minutes}m {seconds}s"
            else:
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                return f"{hours}h {minutes}m"

        except Exception as e:
            logger.error(f"Failed to format elapsed time: {e}")
            return "?"


def main(config_path: str = "config.toml") -> None:
    """Run standalone app.

    Args:
        config_path: Path to TOML config file
    """
    app = SimpleApp(config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
