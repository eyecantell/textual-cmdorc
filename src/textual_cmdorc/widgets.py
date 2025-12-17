"""Command link widget for displaying command status."""

import logging
from pathlib import Path
from cmdorc_frontend.models import TriggerSource, PresentationUpdate

logger = logging.getLogger(__name__)


class CmdorcCommandLink:
    """Widget for displaying a single command with rich tooltip support.

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
        self.current_trigger: TriggerSource = TriggerSource("Idle", "manual", chain=[])
        self.is_running = False
        self._status_icon = "❓"
        self._tooltip = "Idle"
        self._output_path = None

    def apply_update(self, update: PresentationUpdate) -> None:
        """Apply presentation update.

        Args:
            update: PresentationUpdate with new display state
        """
        self._status_icon = update.icon
        self.is_running = update.running
        self._tooltip = update.tooltip
        self._output_path = update.output_path

    def _update_tooltips(self) -> None:
        """Update tooltips with semantic summary, chain, shortcut hint, and duplicate indicator.

        Tooltip structure:
        1. Action line (Stop/Run with semantic summary)
        2. Trigger chain (formatted with truncation if needed)
        3. Keyboard hint (if configured)
        4. Duplicate warning (if applicable)
        """
        if self.is_running:
            self._update_running_tooltip()
        else:
            self._update_idle_tooltip()

    def _update_running_tooltip(self) -> None:
        """Generate tooltip for running command."""
        # Line 1: Action and semantic summary
        semantic = self.current_trigger.get_semantic_summary()
        tooltip = f"Stop — {semantic}"

        # Line 2: Full trigger chain (with left truncation if needed)
        chain_display = self.current_trigger.format_chain(max_width=80)
        tooltip = f"{tooltip}\n{chain_display}"

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
            tooltip = (
                f"{tooltip}\n"
                f"Add shortcut: {self.config.name} = '<key>' in [keyboard] section"
            )

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
        """Set status display.

        Args:
            icon: Status icon
            running: Running state
            tooltip: Tooltip text
        """
        if icon is not None:
            self._status_icon = icon
        if running is not None:
            self.is_running = running
        if tooltip is not None:
            self._tooltip = tooltip

    def set_running(self, running: bool, tooltip: str) -> None:
        """Set running state (for StateReconciler compatibility).

        Args:
            running: Running state
            tooltip: Tooltip text
        """
        self.is_running = running
        self._tooltip = tooltip

    def set_result(self, icon: str, tooltip: str, output_path: Path | None) -> None:
        """Set result display (for StateReconciler compatibility).

        Args:
            icon: Status icon
            tooltip: Tooltip text
            output_path: Path to output file
        """
        self._status_icon = icon
        self.is_running = False
        self._tooltip = tooltip
        self._output_path = output_path

    def action_play_stop(self) -> None:
        """Toggle play/stop action.

        Handled by parent app - this is just a placeholder.
        """
        pass  # Handled by parent app

    # Protocol implementation for StateReconciler
    @property
    def command_name(self) -> str:
        """Get command name (for StateReconciler protocol)."""
        return self.config.name

    def get_label(self) -> str:
        """Generate tree node label with status icon and name.

        Returns:
            Formatted label string for tree display
        """
        # Format: icon + name (+ shortcut if available)
        label = f"{self._status_icon} {self.config.name}"
        if self.keyboard_shortcut:
            label = f"{label} [{self.keyboard_shortcut}]"
        return label
