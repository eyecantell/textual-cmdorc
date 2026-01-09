"""File separator widget for showing command source files."""

from __future__ import annotations

from textual.widgets import Static


class FileSeparator(Static):
    """Visual separator showing source file name.

    Displays a horizontal line with the filename centered, e.g.:
    "━━━━ config.toml ━━━━━━━━━━━━━━━━━━━━━━━━━"

    Used to visually separate commands from different source files
    in multi-config mode.

    Example:
        separator = FileSeparator("build.toml")
    """

    DEFAULT_CSS = """
    FileSeparator {
        height: 1;
        width: 100%;
        color: $text-muted;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        filename: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the file separator.

        Args:
            filename: Name of the source file to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._filename = filename
        self._update_display()

    @property
    def filename(self) -> str:
        """Get the filename being displayed."""
        return self._filename

    def _update_display(self) -> None:
        """Update the display with separator line."""
        # Create a separator line with the filename
        # Format: "━━━━ filename ━━━━━━━━━━━━━━━━━━━━━"
        separator_char = "━"
        prefix = f"{separator_char * 4} "
        suffix = f" {separator_char * 30}"
        self.update(f"{prefix}{self._filename}{suffix}")

    def set_filename(self, filename: str) -> None:
        """Update the displayed filename.

        Args:
            filename: New filename to display
        """
        self._filename = filename
        self._update_display()
