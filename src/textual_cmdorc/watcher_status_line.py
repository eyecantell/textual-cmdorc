"""File watcher status line widget."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual_filelink import FileLink

from textual_cmdorc.formatting import format_time_ago

if TYPE_CHECKING:
    from cmdorc_frontend.watchers import WatcherConfig

logger = logging.getLogger(__name__)


class WatcherStatusLine(Widget):
    """Status line showing file watcher state with click-to-toggle.

    Displays the current state of file watchers and allows users to toggle
    them on/off by clicking anywhere on the status line or using a keyboard shortcut.

    Also shows the last file that triggered a watcher with a clickable FileLink.

    Attributes:
        watcher_count: Number of configured file watchers
        enabled: Whether watchers are currently enabled
        last_file: Path to the last file that triggered
        last_file_time: Timestamp when the last file triggered

    Messages:
        Toggled: Posted when user clicks to toggle watchers
    """

    DEFAULT_CSS = """
    WatcherStatusLine {
        height: auto;
    }
    WatcherStatusLine #watcher-status-container {
        height: auto;
    }
    WatcherStatusLine #watcher-file-link {
        height: auto;
    }
    """

    class Toggled(Message):
        """Posted when user clicks to toggle watchers."""

        pass

    def __init__(
        self,
        watcher_count: int,
        enabled: bool = True,
        command_template: str | None = None,
        watcher_configs: list[WatcherConfig] | None = None,
    ):
        """Initialize watcher status line.

        Args:
            watcher_count: Number of configured file watchers
            enabled: Initial enabled state (default: True)
            command_template: Editor command template for FileLink clicks
            watcher_configs: List of WatcherConfig for tooltip display
        """
        super().__init__()
        self.watcher_count = watcher_count
        self.enabled = enabled
        self.last_file: Path | None = None
        self.last_file_time: float | None = None
        self._command_template = command_template
        self._watcher_configs = watcher_configs or []

    def compose(self):
        """Compose the widget with status line and file info."""
        with Vertical(id="watcher-status-container"):
            yield Static(id="watcher-status-text")
            # FileLink directly in Vertical (no Horizontal wrapper)
            # display_name will include prefix/suffix formatting
            yield FileLink(
                path=Path("/dev/null"),  # Placeholder
                display_name="   (placeholder)",
                id="watcher-file-link",
                command_template=self._command_template,
            )

    def on_mount(self) -> None:
        """Initialize display and start timer."""
        # Hide FileLink initially (will show when file triggers)
        file_link = self.query_one("#watcher-file-link", FileLink)
        file_link.display = False

        # Set tooltip on status text with watcher details
        status_text = self.query_one("#watcher-status-text", Static)
        status_text.tooltip = self._build_watcher_tooltip()

        self._update_display()
        self.set_interval(1.0, self._update_display)

    def _build_watcher_tooltip(self) -> str:
        """Build tooltip showing watched paths and extensions.

        Returns:
            Tooltip text with watcher details.
        """
        if not self._watcher_configs:
            return "No file watchers configured"

        lines = ["File Watchers:"]
        cwd = Path.cwd()

        for config in self._watcher_configs:
            # Try to make path relative to cwd for readability
            try:
                display_path = config.dir.relative_to(cwd)
                path_str = f"./{display_path}"
            except ValueError:
                # Path is not relative to cwd, use absolute
                path_str = str(config.dir)

            # Add recursive indicator
            if config.recursive:
                path_str += "/**"

            # Build extensions string
            ext_str = ", ".join(config.extensions) if config.extensions else "*"

            lines.append(f"  {path_str} [{ext_str}]")

        lines.append("")
        lines.append("Click to toggle watchers on/off")

        return "\n".join(lines)

    def _update_display(self) -> None:
        """Update status text based on current state."""
        # Only update if mounted and app is available
        if not self.is_mounted:
            return

        # Check app context is accessible (may fail during shutdown)
        try:
            _ = self.app
        except Exception:
            logger.debug("App context not accessible (likely during shutdown)")
            return

        try:
            status_text = self.query_one("#watcher-status-text", Static)
            file_link = self.query_one("#watcher-file-link", FileLink)
        except Exception:
            # Widget not ready
            logger.debug("Watcher status widgets not ready for query")
            return

        try:
            if self.enabled:
                status_text.update(f"👁️  File Watchers ({self.watcher_count}) Enabled")

                # Show file info if available
                if self.last_file and self.last_file_time:
                    time_ago = format_time_ago(self.last_file_time)

                    # Update FileLink with path and formatted display_name
                    try:
                        # Include prefix and time suffix in the display_name
                        display_text = f"   ({self.last_file.name} {time_ago})"
                        file_link.set_path(self.last_file, display_name=display_text)
                        file_link.display = True
                    except Exception as e:
                        # Log the error to help debug
                        logger.warning(f"FileLink update failed: {e}")
                        file_link.display = False
                else:
                    file_link.display = False
            else:
                status_text.update("✗ File Watchers Disabled")
                file_link.display = False
        except Exception:
            # Context error (e.g., during app shutdown or from background thread)
            logger.debug("Context error during watcher status update (shutdown/transition)")

    def on_click(self) -> None:
        """Handle click - toggle state and post message."""
        self.enabled = not self.enabled
        self._update_display()
        self.post_message(self.Toggled())

    def on_file_link_clicked(self, event) -> None:
        """Prevent FileLink clicks from toggling watchers."""
        event.stop()

    def set_enabled(self, enabled: bool) -> None:
        """Update enabled state (called from parent widget).

        Args:
            enabled: New enabled state
        """
        if self.enabled != enabled:
            self.enabled = enabled
            self._update_display()

    def set_last_file(self, file_path: Path, timestamp: float) -> None:
        """Update the last triggered file info.

        Args:
            file_path: Path to the file that triggered
            timestamp: Time when the trigger fired
        """
        self.last_file = file_path
        self.last_file_time = timestamp
        self._update_display()
