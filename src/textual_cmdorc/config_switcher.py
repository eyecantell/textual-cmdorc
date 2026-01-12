"""Config switcher widget for multi-config support."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Static


class ConfigSwitcher(Static):
    """Dropdown widget for switching between named configurations.

    Displays the active config name and allows switching via click.
    Posts ConfigSelected message when user selects a different config.

    Example:
        switcher = ConfigSwitcher(
            config_names=["Development", "Production", "Testing"],
            active_name="Development",
        )
    """

    DEFAULT_CSS = """
    ConfigSwitcher {
        height: 1;
        width: 100%;
        padding: 0 1;
        background: $surface;
    }

    ConfigSwitcher:hover {
        background: $surface-darken-1;
    }

    ConfigSwitcher .config-name {
        color: $accent;
        text-style: bold;
    }
    """

    class ConfigSelected(Message):
        """Posted when user selects a different config."""

        def __init__(self, config_name: str) -> None:
            """Initialize with selected config name.

            Args:
                config_name: Name of the selected configuration
            """
            self.config_name = config_name
            super().__init__()

    def __init__(
        self,
        config_names: list[str],
        active_name: str,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the config switcher.

        Args:
            config_names: List of available config names
            active_name: Currently active config name
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._config_names = list(config_names)
        self._active_name = active_name
        self._dropdown_open = False
        self._update_display()

    @property
    def active_name(self) -> str:
        """Get the currently active config name."""
        return self._active_name

    @property
    def config_names(self) -> list[str]:
        """Get list of available config names."""
        return list(self._config_names)

    def _update_display(self) -> None:
        """Update the display text."""
        if self._dropdown_open:
            # Show dropdown with all configs
            lines = []
            for name in self._config_names:
                marker = "●" if name == self._active_name else "○"
                lines.append(f"  {marker} {name}")
            self.update("\n".join(lines))
        else:
            # Show compact view
            self.update(f"Config: {self._active_name} [Switch ▼]")

    def on_click(self) -> None:
        """Handle click - toggle dropdown or select config."""
        if self._dropdown_open:
            # Close dropdown without selection
            self._dropdown_open = False
            self._update_display()
        else:
            # Open dropdown
            self._dropdown_open = True
            self._update_display()

    def select_config(self, name: str) -> None:
        """Select a config by name (programmatic selection).

        Args:
            name: Config name to select
        """
        if name in self._config_names and name != self._active_name:
            self._active_name = name
            self._dropdown_open = False
            self._update_display()
            self.post_message(self.ConfigSelected(name))

    def set_active_silently(self, config_name: str) -> None:
        """Set the active config without posting a message.

        Used when the config is changed externally (e.g., from settings restore).

        Args:
            config_name: Name of the config to set as active
        """
        if config_name in self._config_names:
            self._active_name = config_name
            self._dropdown_open = False
            self._update_display()

    def cycle_next(self) -> None:
        """Cycle to the next config and post selection message."""
        if len(self._config_names) < 2:
            return

        current_idx = self._config_names.index(self._active_name)
        next_idx = (current_idx + 1) % len(self._config_names)
        self.select_config(self._config_names[next_idx])

    def cycle_prev(self) -> None:
        """Cycle to the previous config and post selection message."""
        if len(self._config_names) < 2:
            return

        current_idx = self._config_names.index(self._active_name)
        prev_idx = (current_idx - 1) % len(self._config_names)
        self.select_config(self._config_names[prev_idx])
