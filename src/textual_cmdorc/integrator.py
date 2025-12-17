"""Integrator for wiring controller callbacks to widgets."""

import logging
from typing import Callable

from cmdorc import CommandOrchestrator, RunHandle
from cmdorc_frontend.models import TriggerSource, CommandNode
from textual_cmdorc.widgets import CmdorcCommandLink

logger = logging.getLogger(__name__)


def create_command_link(
    node: CommandNode,
    orchestrator: CommandOrchestrator,
    on_status_change: Callable | None = None,
    keyboard_shortcut: str | None = None,
) -> CmdorcCommandLink:
    """Create a command link and wire orchestrator callbacks.

    Args:
        node: CommandNode
        orchestrator: CommandOrchestrator
        on_status_change: Optional callback for status changes
        keyboard_shortcut: Optional keyboard shortcut key

    Returns:
        Configured CmdorcCommandLink
    """
    link = CmdorcCommandLink(node.config, keyboard_shortcut=keyboard_shortcut)

    def update_from_result(handle: RunHandle, context=None):
        """Update link from run result."""
        result = handle._result if hasattr(handle, "_result") else None
        if result:
            # Extract trigger chain from RunHandle (FIX #4: adapter pattern)
            trigger_chain = handle.trigger_chain if hasattr(handle, "trigger_chain") else []
            trigger_source = TriggerSource.from_trigger_chain(trigger_chain)

            from cmdorc_frontend.models import map_run_state_to_icon, PresentationUpdate

            icon = map_run_state_to_icon(result.state)
            chain_display = trigger_source.format_chain()
            tooltip = f"{result.state.value}\nTrigger chain: {chain_display}"

            update = PresentationUpdate(
                icon=icon,
                running=False,
                tooltip=tooltip,
                output_path=result.output,
            )
            link.apply_update(update)
            link.current_trigger = trigger_source
            link._update_tooltips()

            if on_status_change:
                on_status_change(result.state, result)

    # Wire callbacks
    try:
        orchestrator.set_lifecycle_callback(
            node.name,
            on_success=update_from_result,
            on_failed=update_from_result,
            on_cancelled=update_from_result,
        )
    except Exception as e:
        logger.error(f"Failed to wire callbacks for {node.name}: {e}")

    return link
