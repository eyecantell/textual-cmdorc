"""State reconciliation logic - UI-agnostic command state synchronization."""

import logging
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class CommandView(Protocol):
    """Abstract interface that any frontend must implement to receive state updates."""

    def set_running(self, running: bool, tooltip: str) -> None:
        """Update running state and tooltip.

        Args:
            running: Whether command is currently running
            tooltip: Tooltip text describing the current state
        """
        ...

    def set_result(self, icon: str, tooltip: str, output_path: Path | None) -> None:
        """Update result display with icon, tooltip, and output path.

        Args:
            icon: Status icon (e.g., "✅", "❌", "⏹")
            tooltip: Tooltip text
            output_path: Path to output file if available
        """
        ...

    @property
    def command_name(self) -> str:
        """Get the command name this view represents."""
        ...


class StateReconciler:
    """Reconcile UI state with cmdorc orchestrator state.

    Used on startup and reload to sync view with any existing running commands
    or history. Idempotent and read-only - never triggers execution.
    """

    def __init__(self, orchestrator):
        """Initialize reconciler with orchestrator.

        Args:
            orchestrator: CommandOrchestrator instance
        """
        self.orchestrator = orchestrator

    def reconcile(self, view: CommandView) -> None:
        """Sync view state with orchestrator state.

        Checks for:
        1. Active running handles for the command
        2. Command history if not running

        Args:
            view: CommandView to update
        """
        try:
            # Check for active running handles
            active_handles = self.orchestrator.get_active_handles(view.command_name)

            if active_handles:
                # Command is running
                handle = active_handles[-1]  # Latest handle
                if hasattr(handle, "is_finalized") and handle.is_finalized:
                    # Handle is finalized (completed)
                    self._update_from_result(view, handle)
                else:
                    # Handle is still running
                    comment = getattr(handle, "comment", "Running")
                    view.set_running(True, f"Running: {comment}")
            else:
                # Check history for last result
                history = self.orchestrator.get_history(view.command_name, limit=1)
                if history:
                    result = history[0]
                    icon = self._map_state_icon(result.state)
                    duration = getattr(result, "duration_str", "?")
                    tooltip = f"{result.state.value} ({duration})"
                    output_path = getattr(result, "output", None)
                    view.set_result(icon, tooltip, output_path)
                # else: no history, leave at default idle state
        except Exception as e:
            logger.error(f"Error reconciling state for {view.command_name}: {e}")

    def _update_from_result(self, view: CommandView, handle) -> None:
        """Update view from completed RunHandle.

        Args:
            view: CommandView to update
            handle: RunHandle with result
        """
        result = getattr(handle, "_result", None)
        if result:
            icon = self._map_state_icon(result.state)
            duration = getattr(result, "duration_str", "?")
            tooltip = f"{result.state.value} ({duration})"
            output_path = getattr(result, "output", None)
            view.set_result(icon, tooltip, output_path)

    def _map_state_icon(self, state) -> str:
        """Map cmdorc RunState to icon string.

        Args:
            state: RunState enum value

        Returns:
            Icon string
        """
        from cmdorc_frontend.models import map_run_state_to_icon

        return map_run_state_to_icon(state)
