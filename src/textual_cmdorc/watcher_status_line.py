"""File watcher status line widget."""

from textual.message import Message
from textual.widgets import Static


class WatcherStatusLine(Static):
    """Status line showing file watcher state with click-to-toggle.

    Displays the current state of file watchers and allows users to toggle
    them on/off by clicking anywhere on the line or using a keyboard shortcut.

    Attributes:
        watcher_count: Number of configured file watchers
        enabled: Whether watchers are currently enabled

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
        self._update_display()

    def _update_display(self) -> None:
        """Update status text based on current state."""

        text = f"👁️  File Watchers ({self.watcher_count}) Enabled" if self.enabled else "✗ File Watchers Disabled"
        self.update(text)

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
