"""Command widget using textual-filelink CommandLink."""

import logging
from pathlib import Path

from textual.containers import Horizontal
from textual.widgets import Static
from textual_filelink import CommandLink

logger = logging.getLogger(__name__)


class CmdorcCommandLink(Horizontal):
    """Wrapper for CommandLink with indentation support.

    Displays a command with:
    - Indentation for hierarchy visualization
    - textual-filelink CommandLink widget with play/stop buttons
    - Keyboard shortcut indicator (if configured)
    - Duplicate indicator (if command appears multiple times)

    Features:
    - Real play/stop buttons for command control
    - Status icons with live updates (❓/⏳/✅/❌)
    - Clickable command names (opens result files)
    - Settings icon for future menu implementation
    - Keyboard shortcuts (1, 2, 3, etc.) to trigger commands globally
    """

    DEFAULT_CSS = """
    CmdorcCommandLink {
        width: 100%;
        height: auto;
    }

    CmdorcCommandLink .indent {
        width: auto;
        height: 1;
        color: $text-muted;
    }

    CmdorcCommandLink CommandLink {
        width: 1fr;
    }
    """

    def __init__(
        self,
        command_name: str,
        keyboard_shortcut: str | None = None,
        indent: int = 0,
        is_duplicate: bool = False,
        initial_status_icon: str = "❓",
        output_path: Path | None = None,
    ):
        """Initialize command link with indentation.

        Args:
            command_name: Name of the command
            keyboard_shortcut: Optional keyboard key (e.g., "1", "2")
            indent: Indentation level (0, 1, 2, ...)
            is_duplicate: Whether command appears multiple times in tree
            initial_status_icon: Initial status icon (default: ❓)
            output_path: Path to output file (if any)
        """
        # Initialize command_link BEFORE calling super().__init__()
        # This is critical because Textual's widget init tries to set _tooltip property,
        # which needs command_link to exist (see line ~180)
        self.command_link = None

        super().__init__()

        self.command_name = command_name
        self.keyboard_shortcut = keyboard_shortcut
        self.indent_level = indent
        self.is_duplicate = is_duplicate

        # Build command name display
        display_name = command_name
        if keyboard_shortcut:
            display_name = f"{command_name} [{keyboard_shortcut}]"
        if is_duplicate:
            display_name = f"{display_name} ↳"  # Duplicate indicator

        # Create tooltip
        tooltip = self._build_tooltip()

        # Store the CommandLink widget
        try:
            self.command_link = CommandLink(
                name=command_name,
                output_path=output_path,
                initial_status_icon=initial_status_icon,
                initial_status_tooltip=tooltip,
                show_toggle=False,  # Hide toggle (not needed for cmdorc)
                show_settings=True,  # Show settings icon
                show_remove=False,  # Hide remove (not needed for cmdorc)
            )
        except Exception as e:
            logger.error(
                f"Failed to create CommandLink for '{command_name}': {e}",
                exc_info=True,
            )
            raise

    def compose(self):
        """Compose indentation + command link."""
        # Add indentation spaces
        indent_text = "  " * self.indent_level
        if indent_text:
            yield Static(indent_text, classes="indent")

        # Add the CommandLink widget (only if it was successfully created)
        if self.command_link is not None:
            yield self.command_link

    def _build_tooltip(self) -> str:
        """Build tooltip text."""
        parts = []
        if self.keyboard_shortcut:
            parts.append(f"Press [{self.keyboard_shortcut}] to run/stop")
        if self.is_duplicate:
            parts.append("(Appears in multiple workflows)")
        tooltip_text = "\n".join(parts) if parts else "Not run yet"
        return tooltip_text

    def set_status(
        self,
        icon: str | None = None,
        tooltip: str | None = None,
        running: bool | None = None,
    ) -> None:
        """Update command status.

        Args:
            icon: New status icon (e.g., "✅", "❌")
            tooltip: New tooltip text
            running: Whether command is running (shows spinner)
        """
        if self.command_link is not None:
            self.command_link.set_status(icon=icon, tooltip=tooltip, running=running)

    def set_output_path(self, path: Path | None, tooltip: str | None = None) -> None:
        """Update output file path.

        Args:
            path: Path to output file
            tooltip: Tooltip for the command name link
        """
        if self.command_link is not None:
            self.command_link.set_output_path(path, tooltip=tooltip)

    # Backward compatibility properties
    @property
    def is_running(self) -> bool:
        """Get running state."""
        return getattr(self.command_link, "_running", False)

    @is_running.setter
    def is_running(self, value: bool) -> None:
        """Set running state."""
        if hasattr(self.command_link, "_running"):
            self.command_link._running = value

    @property
    def _status_icon(self) -> str:
        """Get status icon."""
        return getattr(self.command_link, "_status_icon", "❓")

    @_status_icon.setter
    def _status_icon(self, value: str) -> None:
        """Set status icon."""
        if hasattr(self.command_link, "_status_icon"):
            self.command_link._status_icon = value

    @property
    def _tooltip(self) -> str:
        """Get tooltip text."""
        return getattr(self.command_link, "_status_tooltip", "Not run yet")

    @_tooltip.setter
    def _tooltip(self, value: str) -> None:
        """Set tooltip text."""
        if hasattr(self.command_link, "_status_tooltip"):
            self.command_link._status_tooltip = value

    @property
    def _output_path(self) -> Path | None:
        """Get output path."""
        return getattr(self.command_link, "_output_path", None)

    @_output_path.setter
    def _output_path(self, value: Path | None) -> None:
        """Set output path."""
        if hasattr(self.command_link, "_output_path"):
            self.command_link._output_path = value


# Backward compatibility: Old data class-based CmdorcCommandLink for legacy code
class CmdorcCommandLinkData:
    """Widget for displaying a single command with rich tooltip support (legacy data class).

    This is the old data class-based implementation, kept for backward compatibility.
    New code should use the CmdorcCommandLink Textual widget instead.

    Features:
    - Semantic trigger summaries in tooltips
    - Full trigger chain display with truncation
    - Keyboard shortcut hints
    - Duplicate command indicators
    - Output path tracking
    """

    def __init__(
        self,
        config,
        keyboard_shortcut: str | None = None,
        is_duplicate: bool = False,
    ):
        """Initialize command link.

        Args:
            config: CommandConfig
            keyboard_shortcut: Optional keyboard shortcut key
            is_duplicate: Whether this command appears multiple times in tree
        """
        self.config = config
        self.keyboard_shortcut = keyboard_shortcut
        self.is_duplicate = is_duplicate
        self.current_trigger = None
        self.is_running = False
        self._status_icon = "❓"
        self._tooltip = "Idle"
        self._output_path = None

    def apply_update(self, update) -> None:
        """Apply presentation update."""
        self._status_icon = update.icon
        self.is_running = update.running
        self._tooltip = update.tooltip
        self._output_path = update.output_path

    def _update_tooltips(self) -> None:
        """Update tooltips with semantic summary, chain, shortcut hint, and duplicate indicator."""
        if self.is_running:
            self._update_running_tooltip()
        else:
            self._update_idle_tooltip()

    def _update_running_tooltip(self) -> None:
        """Generate tooltip for running command."""
        # Line 1: Action and semantic summary
        if self.current_trigger:
            semantic = self.current_trigger.get_semantic_summary()
            tooltip = f"Stop — {semantic}"

            # Line 2: Full trigger chain (with left truncation if needed)
            chain_display = self.current_trigger.format_chain(max_width=80)
            tooltip = f"{tooltip}\n{chain_display}"
        else:
            tooltip = "Stop"

        # Line 3: Keyboard hint (if configured)
        if self.keyboard_shortcut:
            tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to stop"

        # Line 4: Duplicate indicator (if applicable)
        if self.is_duplicate:
            tooltip = f"{tooltip}\n(Appears in multiple workflows - shortcut affects all)"

        self._tooltip = tooltip

    def _update_idle_tooltip(self) -> None:
        """Generate tooltip for idle command."""
        # Line 1: Trigger list and manual option
        triggers = ", ".join(self.config.triggers) if self.config.triggers else "none"
        tooltip = f"Run (Triggers: {triggers} | manual)"

        # Line 2: Keyboard hint (if configured) or setup hint (if not)
        if self.keyboard_shortcut:
            tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to run"
        else:
            # User-friendly hint for configuring shortcut
            tooltip = f"{tooltip}\nAdd shortcut: {self.config.name} = '<key>' in [keyboard] section"

        # Line 3: Duplicate indicator (if applicable)
        if self.is_duplicate:
            tooltip = f"{tooltip}\n(Appears in multiple workflows - shortcut affects all)"

        self._tooltip = tooltip

    def set_status(
        self,
        icon: str | None = None,
        running: bool | None = None,
        tooltip: str | None = None,
    ) -> None:
        """Set status display."""
        if icon is not None:
            self._status_icon = icon
        if running is not None:
            self.is_running = running
        if tooltip is not None:
            self._tooltip = tooltip

    def set_running(self, running: bool, tooltip: str) -> None:
        """Set running state."""
        self.is_running = running
        self._tooltip = tooltip

    def set_result(self, icon: str, tooltip: str, output_path: Path | None) -> None:
        """Set result display."""
        self._status_icon = icon
        self.is_running = False
        self._tooltip = tooltip
        self._output_path = output_path

    def action_play_stop(self) -> None:
        """Toggle play/stop action."""
        pass

    @property
    def command_name(self) -> str:
        """Get command name."""
        return self.config.name

    def get_label(self) -> str:
        """Generate tree node label with status icon and name."""
        label = f"{self._status_icon} {self.config.name}"
        if self.keyboard_shortcut:
            label = f"{label} [{self.keyboard_shortcut}]"
        return label
