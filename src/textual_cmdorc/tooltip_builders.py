"""Tooltip builders for textual-cmdorc.

Responsible for constructing all tooltip content shown in the TUI.
Separated from SimpleApp to improve testability and maintainability.
"""

import logging

from cmdorc import RunHandle

from cmdorc_frontend.models import TriggerSource
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter

from .formatting import format_elapsed_time, get_output_preview

logger = logging.getLogger(__name__)


class TooltipBuilder:
    """Builds formatted tooltips for command UI elements.

    Responsibilities:
    - Status icon tooltips (run history and results)
    - Play/Stop button tooltips (trigger conditions and chains)
    - Command name tooltips (output file preview)
    """

    def __init__(self, adapter: OrchestratorAdapter):
        """Initialize tooltip builder.

        Args:
            adapter: OrchestratorAdapter for accessing command state
        """
        self.adapter = adapter

    # ========================================================================
    # Status Icon Tooltip Builders (Run History)
    # ========================================================================

    def build_status_tooltip_idle(self, cmd_name: str) -> str:
        """Build tooltip for idle command status icon.

        Shows:
        - History if available (loaded from disk)
        - "Not yet run" if no history

        Args:
            cmd_name: Command name

        Returns:
            Formatted tooltip string
        """
        try:
            lines = [cmd_name, "─" * len(cmd_name)]

            # Check for historical runs loaded from disk
            history = self.adapter.orchestrator.get_history(cmd_name, limit=3)

            if history and len(history) > 0:
                # Show historical runs (already in reverse chronological order from cmdorc 0.8.1+)
                if len(history) > 1:
                    lines.append("Last 3 runs:")
                else:
                    lines.append("Last run:")

                for result in history:
                    # Status icon
                    icon = {
                        "SUCCESS": "✅",
                        "FAILED": "❌",
                        "CANCELLED": "⚠️",
                    }.get(result.state.name, "◯")

                    # Time ago and duration (from cmdorc)
                    ago = result.time_ago_str or "?"
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

    def build_status_tooltip_running(self, cmd_name: str, handle: RunHandle | None) -> str:
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
        try:
            lines = [cmd_name, "─" * len(cmd_name)]

            # Elapsed time
            if handle and handle.start_time:
                elapsed = format_elapsed_time(handle.start_time)
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

    def build_status_tooltip_completed(self, cmd_name: str, handle: RunHandle) -> str:
        """Build tooltip for completed command status icon.

        Shows:
        - Last 3 runs with status, time ago, duration
        - Resolved command

        Args:
            cmd_name: Command name
            handle: RunHandle with result

        Returns:
            Formatted tooltip string
        """
        try:
            lines = [cmd_name, "─" * len(cmd_name)]

            # Try to get history (last 3 runs)
            history = self.adapter.orchestrator.get_history(cmd_name, limit=3)

            if history and len(history) > 1:
                # Show last 3 runs (already in reverse chronological order from cmdorc 0.8.1+)
                lines.append("Last 3 runs:")
                for result in history:
                    # Status icon
                    icon = {
                        "SUCCESS": "✅",
                        "FAILED": "❌",
                        "CANCELLED": "⚠️",
                    }.get(result.state.name, "◯")

                    # Time ago and duration (from cmdorc)
                    ago = result.time_ago_str or "?"
                    duration = result.duration_str or "?"

                    lines.append(f"  {icon} {ago} for {duration}")
            else:
                # Single run info (from cmdorc)
                icon = {"SUCCESS": "✅", "FAILED": "❌", "CANCELLED": "⚠️"}.get(handle.state.name, "◯")
                ago = handle.time_ago_str or "?"
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

    def build_play_tooltip(self, cmd_name: str) -> str:
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

    def build_stop_tooltip(self, cmd_name: str, handle: RunHandle | None) -> str:
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
        try:
            lines = [f"⏹️ Stop {cmd_name}", ""]

            # Elapsed time
            if handle and handle.start_time:
                elapsed = format_elapsed_time(handle.start_time)
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

    def build_output_tooltip(self, cmd_name: str, is_running: bool = False) -> str:
        """Build tooltip for command name (output preview).

        Shows:
        - Output file path
        - Last 5 lines of output (always, even if file > 5 lines)
        - Click hint

        Args:
            cmd_name: Command name
            is_running: True if command is currently running

        Returns:
            Formatted tooltip string
        """
        try:
            lines = [cmd_name, ""]

            # Get output file from latest result
            status = self.adapter.orchestrator.get_status(cmd_name)
            if not status or not status.last_run or not status.last_run.output_file:
                lines.append("No output available yet")
                return "\n".join(lines)

            output_file = status.last_run.output_file

            # Don't show historical output info if command is currently running
            if is_running:
                lines.append("Command running - output will be available after completion")
                return "\n".join(lines)

            # Get preview using formatting utility
            preview_data = get_output_preview(output_file, max_lines=1, max_line_length=60)

            if not preview_data:
                lines.append("No output available yet")
                return "\n".join(lines)

            preview_lines, total_lines = preview_data

            # Textual tooltips will not render properly if they are too many lines (they will flash and disappear), so these have been commented out for now.
            # Show preview (last 5 lines)
            # if preview_lines:
            #    lines.append("Last 5 lines:")
            #    lines.append("─" * 40)
            #    lines.extend(preview_lines)
            #    lines.append("─" * 40)
            # else:
            #    lines.append("(empty output)")
            #    lines.append("─" * 40)

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
    # Helper Methods
    # ========================================================================

    def _get_command_string(self, cmd_name: str) -> str:
        """Get resolved command string for a command using preview_command().

        Args:
            cmd_name: Command name

        Returns:
            Resolved command string or error message
        """
        try:
            preview = self.adapter.orchestrator.preview_command(cmd_name)
            return preview.command
        except Exception as e:
            logger.error(f"Failed to get command string for {cmd_name}: {e}")
            return f"Error: {e}"

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
            logger.error(f"Failed to get downstream for {cmd_name}: {e}")
            return []
