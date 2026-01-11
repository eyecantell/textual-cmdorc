"""File watcher status line widget."""

from pathlib import Path

from textual.message import Message
from textual.widgets import Static

from textual_cmdorc.formatting import format_time_ago


class WatcherStatusLine(Static):
    """Status line showing file watcher state with click-to-toggle.

    Displays the current state of file watchers and allows users to toggle
    them on/off by clicking anywhere on the line or using a keyboard shortcut.

    Also shows the last file that triggered a watcher with a timer.

    Attributes:
        watcher_count: Number of configured file watchers
        enabled: Whether watchers are currently enabled
        last_file: Path to the last file that triggered (relative)
        last_file_time: Timestamp when the last file triggered

    Messages:
        Toggled: Posted when user clicks to toggle watchers
    """

    class Toggled(Message):
        """Posted when user clicks to toggle watchers."""

        pass

    def __init__(self, watcher_count: int, enabled: bool = True):
        """Initialize watcher status line.

        Args:
            watcher_count: Number of configured file watchers
            enabled: Initial enabled state (default: True)
        """
        super().__init__()
        self.watcher_count = watcher_count
        self.enabled = enabled
        self.last_file: Path | None = None
        self.last_file_time: float | None = None
        self._update_display()

    def _update_display(self) -> None:
        """Update status text based on current state."""
        if self.enabled:
            text = f"👁️  File Watchers ({self.watcher_count}) Enabled"
            # Add last triggered file info on second line if available
            if self.last_file and self.last_file_time:
                time_ago = format_time_ago(self.last_file_time)
                # Try to get relative path, fall back to name
                try:
                    rel_path = self.last_file.relative_to(Path.cwd())
                except ValueError:
                    rel_path = self.last_file.name
                text += f"\n   {rel_path} {time_ago}"
        else:
            text = "✗ File Watchers Disabled"
        self.update(text)

    def on_mount(self) -> None:
        """Start timer to refresh the time display."""
        self.set_interval(1.0, self._update_display)

    def on_click(self) -> None:
        """Handle click - toggle state and post message."""
        self.enabled = not self.enabled
        self._update_display()
        self.post_message(self.Toggled())

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
