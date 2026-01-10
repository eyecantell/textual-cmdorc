"""Command details modal screen for textual-cmdorc.

Displays comprehensive information about a command including:
- Status and last run results
- Current run state (if running)
- Trigger configuration and downstream commands
- Run history
- Output file preview
- Configuration details
"""

import logging
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static
from textual_filelink import FileLink

from cmdorc_frontend.models import TriggerSource
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter

from .formatting import format_elapsed_time, get_output_preview

logger = logging.getLogger(__name__)


class CommandDetailsScreen(ModalScreen):
    """Modal screen showing detailed command information.

    Features:
    - Live updates every 2 seconds
    - Keyboard shortcuts for common actions
    - Automatic refresh on command state changes

    Keyboard shortcuts:
    - Esc/q: Close modal
    - o: Open output file in $EDITOR
    - r: Run command
    - c: Copy resolved command to clipboard
    - e: Edit command (placeholder)
    """

    DEFAULT_CSS = """
    CommandDetailsScreen {
        align: center middle;
    }

    CommandDetailsScreen > VerticalScroll {
        width: 80;
        max-height: 90%;
        background: $panel;
        border: solid $accent;
        padding: 2;
    }

    .details-header {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    .details-section {
        margin-bottom: 1;
    }

    .details-section-title {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    .details-separator {
        color: $text-muted;
    }

    .details-footer {
        text-style: italic;
        color: $text-muted;
        margin-top: 1;
        text-align: center;
    }

    /* FileLink styling within modal */
    CommandDetailsScreen FileLink {
        margin-left: 2;
        padding: 0 1;
    }

    CommandDetailsScreen FileLink:hover {
        background: $accent 20%;
    }
    """

    BINDINGS = [
        ("escape,q", "dismiss", "Close"),
        ("o", "open_output", "Open output"),
        ("r", "run_command", "Run command"),
        ("c", "copy_command", "Copy command"),
        ("e", "edit_command", "Edit config"),
    ]

    def __init__(self, cmd_name: str, adapter: OrchestratorAdapter, **kwargs):
        """Initialize details screen.

        Args:
            cmd_name: Command name to display details for
            adapter: OrchestratorAdapter instance for accessing command data
        """
        super().__init__(**kwargs)
        self.cmd_name = cmd_name
        self.adapter = adapter
        self._refresh_timer = None
        self._callback_ids = []  # Track registered callbacks for cleanup

    def compose(self) -> ComposeResult:
        """Compose modal content with all sections."""
        with VerticalScroll():
            # Header
            yield Static(f"Command Details: {self.cmd_name}", classes="details-header", id="details-header")

            # Status section
            yield Static("", id="status-section")

            # Current run section (conditionally shown)
            yield Static("", id="current-run-section")

            # Triggers section
            yield Static("", id="triggers-section")

            # Run history section
            yield Static("", id="history-section")

            # Output section with embedded FileLink
            with Vertical(id="output-section-container", classes="details-section"):
                yield Static("", id="output-section-text")
                yield FileLink(
                    path=Path("/dev/null"),  # Placeholder, updated in on_mount
                    _embedded=True,
                    id="output-file-link",
                    tooltip="Press 'o' to open in editor",
                    command_template=self.adapter.get_editor_command_template(),
                )

            # Configuration section with embedded FileLink
            with Vertical(id="config-section-container", classes="details-section"):
                yield Static("", id="config-section-text")
                yield FileLink(
                    path=self.adapter.config_path,
                    _embedded=True,
                    id="config-file-link",
                    tooltip="Press 'e' to edit configuration",
                    command_template=self.adapter.get_editor_command_template(),
                )

            # Footer with keyboard hints
            yield Static(
                "Press 'o' to open output | 'r' to run | 'c' to copy command | 'e' to edit config | 'q' to close",
                classes="details-footer",
                id="details-footer",
            )

    async def on_mount(self) -> None:
        """Initialize timer and callbacks on mount."""
        try:
            # Initial content refresh
            self._refresh_content()

            # Start 2-second update timer
            self._refresh_timer = self.set_interval(2.0, self._refresh_content)

            # Wire orchestrator callbacks for real-time updates
            # Note: cmdorc's on_event returns None, can't track callback IDs
            # We'll rely on screen dismissal to stop receiving updates
            self.adapter.orchestrator.on_event(
                f"command_started:{self.cmd_name}",
                lambda h, ctx: self._refresh_content(),
            )
            self.adapter.on_command_success(
                self.cmd_name,
                lambda h: self._refresh_content(),
            )
            self.adapter.on_command_failed(
                self.cmd_name,
                lambda h: self._refresh_content(),
            )
            self.adapter.on_command_cancelled(
                self.cmd_name,
                lambda h: self._refresh_content(),
            )

        except Exception as e:
            logger.error(f"Failed to mount details screen: {e}", exc_info=True)

    async def on_unmount(self) -> None:
        """Clean up timer on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    def _refresh_content(self) -> None:
        """Refresh all content sections.

        Called by timer (every 2 seconds) and orchestrator callbacks.
        """
        # Don't refresh if screen is not mounted or being dismissed
        if not self.is_mounted:
            return

        try:
            # Update each section
            self.query_one("#status-section", Static).update(self._build_status_section())

            # Current run section - only show if running
            current_run_content = self._build_current_run_section()
            current_run_widget = self.query_one("#current-run-section", Static)
            if current_run_content:
                current_run_widget.update(current_run_content)
                current_run_widget.display = True
            else:
                current_run_widget.display = False

            self.query_one("#triggers-section", Static).update(self._build_triggers_section())
            self.query_one("#history-section", Static).update(self._build_history_section())

            # Update Output section (text + FileLink)
            output_text, output_path = self._build_output_section_parts()
            self.query_one("#output-section-text", Static).update(output_text)

            output_link = self.query_one("#output-file-link", FileLink)
            if output_path:
                output_link.set_path(output_path)  # In-place update
                output_link.display = True
            else:
                output_link.display = False

            # Update Config section (text only, path is static)
            config_text = self._build_config_section_text()
            self.query_one("#config-section-text", Static).update(config_text)

        except Exception as e:
            # Log error but don't dismiss - individual sections handle their own errors
            logger.error(f"Failed to refresh content for {self.cmd_name}: {e}", exc_info=True)

    # ========================================================================
    # Content Builder Methods
    # ========================================================================

    def _build_status_section(self) -> str:
        """Build status section content."""
        try:
            lines = ["Status", "─" * 40]

            status = self.adapter.orchestrator.get_status(self.cmd_name)
            if not status or not status.last_run:
                lines.append("◯ Not yet run")
                return "\n".join(lines)

            last_run = status.last_run

            # Status icon and state
            icon = {"SUCCESS": "✅", "FAILED": "❌", "CANCELLED": "⚠️"}.get(last_run.state.name, "◯")
            state_name = last_run.state.name.title()
            time_ago = last_run.time_ago_str or "?"

            lines.append(f"{icon} {state_name} – {time_ago}")

            # Duration
            duration = last_run.duration_str or "?"
            lines.append(f"Duration: {duration}")

            # Exit code (for failed commands)
            return_code = getattr(last_run, "return_code", None)
            if return_code is not None:
                lines.append(f"Exit code: {return_code}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build status section: {e}")
            return "Status\n" + "─" * 40 + "\nError loading status"

    def _build_current_run_section(self) -> str | None:
        """Build current run section content (only if running)."""
        try:
            status = self.adapter.orchestrator.get_status(self.cmd_name)

            # Check if command is currently running
            if not status or not status.last_run or status.last_run.state.name not in ["RUNNING"]:
                return None  # Don't show section when not running

            lines = ["Current Run", "─" * 40]

            last_run = status.last_run

            # Elapsed time
            if last_run.start_time:
                elapsed = format_elapsed_time(last_run.start_time.timestamp())
                start_clock_time = last_run.start_time.strftime("%I:%M %p")
                lines.append(f"⏳ Running for {elapsed}")
                lines.append(f"Started: {start_clock_time}")
            else:
                lines.append("⏳ Running...")

            lines.append("")

            # Trigger chain
            if last_run.trigger_chain:
                trigger_source = TriggerSource.from_trigger_chain(last_run.trigger_chain)
                semantic = trigger_source.get_semantic_summary()
                lines.append(f"Trigger: {semantic}")

                # Show chain if multiple hops
                if len(last_run.trigger_chain) > 1:
                    chain_formatted = " → ".join(last_run.trigger_chain)
                    lines.append(f"  → {chain_formatted}")

            lines.append("")

            # Resolved command
            if last_run.resolved_command:
                lines.append(f"Command: {last_run.resolved_command.command}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build current run section: {e}")
            return None

    def _build_triggers_section(self) -> str:
        """Build triggers section content."""
        try:
            lines = ["Triggers", "─" * 40]

            # Get command config
            config = self.adapter.orchestrator._runtime.get_command(self.cmd_name)
            if not config:
                lines.append("No trigger configuration found")
                return "\n".join(lines)

            # List triggers with semantic formatting
            if config.triggers:
                for trigger in config.triggers:
                    if trigger.startswith("command_success:"):
                        trigger_cmd = trigger.split(":", 1)[1]
                        lines.append(f"• After {trigger_cmd} succeeds")
                    elif trigger.startswith("command_failed:"):
                        trigger_cmd = trigger.split(":", 1)[1]
                        lines.append(f"• After {trigger_cmd} fails")
                    else:
                        lines.append(f"• {trigger}")

            # Manual trigger with keyboard shortcut
            shortcut = self.adapter.keyboard_config.shortcuts.get(self.cmd_name)
            if shortcut:
                lines.append(f"• manual ([{shortcut}])")
            else:
                lines.append("• manual")

            # Downstream commands (on success)
            downstream_success = self._get_downstream_commands(self.cmd_name, "success")
            if downstream_success:
                lines.append("")
                lines.append("On success →")
                for cmd in downstream_success[:3]:
                    lines.append(f"  → {cmd}")
                if len(downstream_success) > 3:
                    lines.append(f"  ... and {len(downstream_success) - 3} more")

            # Downstream commands (on failure)
            downstream_failure = self._get_downstream_commands(self.cmd_name, "failed")
            if downstream_failure:
                lines.append("")
                lines.append("On failure →")
                for cmd in downstream_failure[:3]:
                    lines.append(f"  → {cmd}")
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
            logger.error(f"Failed to build triggers section: {e}")
            return "Triggers\n" + "─" * 40 + "\nError loading triggers"

    def _build_history_section(self) -> str:
        """Build run history section content."""
        try:
            lines = ["", "Run History", "─" * 40]

            # Get command config for keep_in_memory
            config = self.adapter.orchestrator._runtime.get_command(self.cmd_name)
            limit = config.keep_in_memory if config else 3

            # Get history
            history = self.adapter.orchestrator.get_history(self.cmd_name, limit=limit)

            if not history or len(history) == 0:
                lines.append("No runs recorded")
                return "\n".join(lines)

            # Format each run (already in reverse chronological order from cmdorc 0.8.1+)
            for result in history:
                icon = {"SUCCESS": "✅", "FAILED": "❌", "CANCELLED": "⚠️"}.get(result.state.name, "◯")
                time_ago = result.time_ago_str or "?"
                duration = result.duration_str or "?"

                # Format: ✅ 5s ago     1.2s      exit 0
                line = f"{icon} {time_ago:12s} {duration:10s}"
                return_code = getattr(result, "return_code", None)
                if return_code is not None and result.state.name == "FAILED":
                    line += f" exit {return_code}"
                lines.append(line)

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build history section: {e}")
            return "Run History\n" + "─" * 40 + "\nError loading history"

    def _build_output_section_parts(self) -> tuple[str, Path | None]:
        """Build output section content, returning text and file path separately.

        Returns:
            tuple: (text_content, file_path)
        """
        try:
            lines = ["", "Output", "─" * 40]

            # Get latest run output file
            status = self.adapter.orchestrator.get_status(self.cmd_name)
            if not status or not status.last_run or not status.last_run.output_file:
                lines.append("No output available")
                return "\n".join(lines), None

            output_file = status.last_run.output_file

            # Add "File:" label (FileLink will be rendered separately)
            lines.append("File:")
            lines.append("")  # Spacing for FileLink widget
            lines.append("")

            # Get output preview
            preview_data = get_output_preview(output_file, max_lines=15, max_line_length=80)

            if not preview_data:
                lines.append("(output file not found)")
                return "\n".join(lines), output_file  # Still return path

            preview_lines, total_lines = preview_data

            if preview_lines:
                lines.append("Preview (last 15 lines):")
                lines.append("─" * 40)
                lines.extend(preview_lines)
                lines.append("─" * 40)
            else:
                lines.append("(empty output)")

            lines.append("")

            if total_lines > 15:
                lines.append(f"[{total_lines} total lines – press 'o' to open full file]")
            else:
                lines.append("Press 'o' to open in editor")

            return "\n".join(lines), output_file

        except Exception as e:
            logger.error(f"Failed to build output section: {e}")
            return "Output\n" + "─" * 40 + "\nError loading output", None

    def _build_config_section_text(self) -> str:
        """Build configuration section text content (FileLink rendered separately).

        Returns:
            Text content without file path line
        """
        try:
            lines = ["", "Configuration", "─" * 40]

            # Add "File:" label (FileLink will be rendered separately)
            lines.append("File:")
            lines.append("")  # Spacing for FileLink widget
            lines.append("")

            # Get command config
            config = self.adapter.orchestrator._runtime.get_command(self.cmd_name)
            if not config:
                lines.append("No configuration found")
                return "\n".join(lines)

            # Resolved command
            try:
                preview = self.adapter.orchestrator.preview_command(self.cmd_name)
                lines.append(f"Command: {preview.command}")
            except Exception as e:
                logger.warning(f"Failed to preview command: {e}")
                lines.append(f"Command: {config.command}")

            # Working directory
            if config.cwd:
                lines.append(f"Working directory: {config.cwd}")

            lines.append("")

            # Non-default config values
            non_defaults = []
            if config.timeout_secs is not None:
                non_defaults.append(f"Timeout: {config.timeout_secs}s")
            if config.max_concurrent != 1:
                non_defaults.append(f"Max concurrent: {config.max_concurrent}")
            if config.debounce_in_ms != 0:
                mode = config.debounce_mode or "start"
                non_defaults.append(f"Debounce: {config.debounce_in_ms}ms (mode: {mode})")
            if config.on_retrigger != "cancel_and_restart":
                non_defaults.append(f"On retrigger: {config.on_retrigger}")
            if config.keep_in_memory != 3:
                non_defaults.append(f"Keep in memory: {config.keep_in_memory} runs")

            if non_defaults:
                for item in non_defaults:
                    lines.append(item)
                lines.append("")

            # File watchers that trigger this command
            relevant_watchers = [w for w in self.adapter._watchers if w.trigger_emitted in config.triggers]

            if relevant_watchers:
                lines.append("")
                lines.append("File watchers:")
                for watcher in relevant_watchers:
                    lines.append(f"  • dir: {watcher.dir}")
                    if watcher.extensions:
                        extensions_str = ", ".join(watcher.extensions)
                        lines.append(f"    extensions: {extensions_str}")
                    if watcher.recursive:
                        lines.append("    recursive: true")
                    lines.append(f"    trigger_emitted: {watcher.trigger_emitted}")
                    lines.append(f"    debounce: {watcher.debounce_ms}ms")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to build config section: {e}")
            return "Configuration\n" + "─" * 40 + "\nError loading configuration"

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _get_downstream_commands(self, cmd_name: str, trigger_type: str = "success") -> list[str]:
        """Get commands triggered after success/failure.

        Args:
            cmd_name: Command name
            trigger_type: "success" or "failed"

        Returns:
            List of downstream command names
        """
        try:
            trigger_graph = self.adapter.orchestrator.get_trigger_graph()
            trigger_key = f"command_{trigger_type}:{cmd_name}"
            return trigger_graph.get(trigger_key, [])
        except Exception as e:
            logger.error(f"Failed to get downstream commands: {e}")
            return []

    # ========================================================================
    # Keyboard Actions
    # ========================================================================

    async def action_open_output(self) -> None:
        """Open latest output file by activating FileLink widget."""
        try:
            output_link = self.query_one("#output-file-link", FileLink)

            if not output_link.display:
                if self.app:
                    self.app.notify("No output file available", severity="warning")
                return

            # Programmatically activate FileLink
            output_link.open_file()

        except Exception as e:
            logger.error(f"Failed to open output: {e}")
            if self.app:
                self.app.notify(f"Failed to open editor: {e}", severity="error")

    async def action_run_command(self) -> None:
        """Run command via adapter."""
        try:
            self.adapter.request_run(self.cmd_name)
            if self.app:
                self.app.notify(f"Running {self.cmd_name}...")
        except Exception as e:
            logger.error(f"Failed to run command: {e}")
            if self.app:
                self.app.notify(f"Failed to run command: {e}", severity="error")

    async def action_copy_command(self) -> None:
        """Copy resolved command to clipboard."""
        try:
            preview = self.adapter.orchestrator.preview_command(self.cmd_name)
            if self.app:
                self.app.copy_to_clipboard(preview.command)
                self.app.notify("Command copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy command: {e}")
            if self.app:
                self.app.notify(f"Failed to copy command: {e}", severity="error")

    async def action_edit_command(self) -> None:
        """Open config file for editing by activating FileLink widget."""
        try:
            config_link = self.query_one("#config-file-link", FileLink)

            # Programmatically activate FileLink
            config_link.open_file()

        except Exception as e:
            logger.error(f"Failed to open config: {e}")
            if self.app:
                self.app.notify(f"Failed to open editor: {e}", severity="error")
