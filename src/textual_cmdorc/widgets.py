"""Command link widget for displaying command status."""

from pathlib import Path
from cmdorc_frontend.models import TriggerSource, PresentationUpdate


class CmdorcCommandLink:
    """Widget for displaying a single command."""

    def __init__(self, config, keyboard_shortcut: str | None = None, is_duplicate: bool = False):
        """Initialize command link.

        Args:
            config: CommandConfig
            keyboard_shortcut: Optional keyboard shortcut key
            is_duplicate: Whether this command appears multiple times in tree
        """
        self.config = config
        self.keyboard_shortcut = keyboard_shortcut
        self.is_duplicate = is_duplicate
        self.current_trigger: TriggerSource = TriggerSource("Idle", "manual", chain=[])
        self.is_running = False
        self._status_icon = "❓"
        self._tooltip = "Idle"
        self._output_path = None

    def apply_update(self, update: PresentationUpdate) -> None:
        """Apply presentation update."""
        self._status_icon = update.icon
        self.is_running = update.running
        self._tooltip = update.tooltip
        self._output_path = update.output_path

    def _update_tooltips(self) -> None:
        """Update tooltips with semantic summary and chain."""
        if self.is_running:
            semantic = self.current_trigger.get_semantic_summary()
            chain_display = self.current_trigger.format_chain()
            tooltip = f"Stop — {semantic}\n{chain_display}"
            if self.keyboard_shortcut:
                tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to stop"
            if self.is_duplicate:
                tooltip = f"{tooltip}\n(Appears in multiple workflows - shortcut affects all instances)"
            self._tooltip = tooltip
        else:
            triggers = ", ".join(self.config.triggers) or "none"
            tooltip = f"Run (Triggers: {triggers} | manual)"
            if self.keyboard_shortcut:
                tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to run"
            else:
                tooltip = (
                    f"{tooltip}\nSet hotkey with {self.config.name} = '<key>' in [keyboard] shortcuts"
                )
            if self.is_duplicate:
                tooltip = f"{tooltip}\n(Appears in multiple workflows - shortcut affects all instances)"
            self._tooltip = tooltip

    def set_status(self, icon: str | None = None, running: bool | None = None, tooltip: str | None = None) -> None:
        """Set status display."""
        if icon is not None:
            self._status_icon = icon
        if running is not None:
            self.is_running = running
        if tooltip is not None:
            self._tooltip = tooltip

    def action_play_stop(self) -> None:
        """Toggle play/stop."""
        pass  # Handled by parent app
