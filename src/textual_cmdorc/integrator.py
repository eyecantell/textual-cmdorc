"""Integrator for wiring controller callbacks to widgets.

Handles:
- FIX #4: Adapter pattern to keep models UI-agnostic
- FIX #2: Duplicate tracking integration
- Enhanced tooltip generation with semantic summaries
- StateReconciler integration for startup sync
"""

import logging
from typing import Callable

from cmdorc import CommandOrchestrator, RunHandle
from cmdorc_frontend.models import TriggerSource, CommandNode, PresentationUpdate, map_run_state_to_icon
from cmdorc_frontend.state_manager import StateReconciler
from textual_cmdorc.widgets import CmdorcCommandLink

logger = logging.getLogger(__name__)


def create_command_link(
    node: CommandNode,
    orchestrator: CommandOrchestrator,
    on_status_change: Callable | None = None,
    keyboard_shortcut: str | None = None,
    reconcile_on_create: bool = True,
) -> CmdorcCommandLink:
    """Create a command link and wire orchestrator callbacks.

    FIX #4: Adapter pattern - models stay UI-agnostic, integration happens here.

    Args:
        node: CommandNode
        orchestrator: CommandOrchestrator
        on_status_change: Optional callback for status changes
        keyboard_shortcut: Optional keyboard shortcut key
        reconcile_on_create: If True, sync initial state from orchestrator

    Returns:
        Configured CmdorcCommandLink with callbacks wired
    """
    link = CmdorcCommandLink(node.config, keyboard_shortcut=keyboard_shortcut)

    def update_from_run_handle(handle: RunHandle, context=None) -> None:
        """Update link from completed RunHandle.

        FIX #4: Adapter extracts data from RunHandle, converts to domain models.
        """
        result = handle._result if hasattr(handle, "_result") else None
        if result:
            # FIX #4: Extract trigger chain and create domain model (keeps models UI-agnostic)
            trigger_chain = handle.trigger_chain if hasattr(handle, "trigger_chain") else []
            trigger_source = TriggerSource.from_trigger_chain(trigger_chain)

            # Create presentation update
            icon = map_run_state_to_icon(result.state)
            duration = getattr(result, "duration_str", "?")
            tooltip = f"{result.state.value} ({duration})"
            output_path = getattr(result, "output", None)

            # Apply to view
            update = PresentationUpdate(
                icon=icon,
                running=False,
                tooltip=tooltip,
                output_path=output_path,
            )
            link.apply_update(update)
            link.current_trigger = trigger_source
            link._update_tooltips()

            if on_status_change:
                on_status_change(result.state, result)

    def update_on_running(handle: RunHandle) -> None:
        """Update link when command starts running.

        Shows semantic summary and trigger chain.
        """
        # Extract trigger chain
        trigger_chain = handle.trigger_chain if hasattr(handle, "trigger_chain") else []
        trigger_source = TriggerSource.from_trigger_chain(trigger_chain)
        link.current_trigger = trigger_source

        semantic = trigger_source.get_semantic_summary()
        tooltip = f"Running — {semantic}\n{trigger_source.format_chain()}"
        link.set_running(True, tooltip)

    # Wire callbacks
    try:
        orchestrator.set_lifecycle_callback(
            node.name,
            on_success=update_from_run_handle,
            on_failed=update_from_run_handle,
            on_cancelled=update_from_run_handle,
        )
    except Exception as e:
        logger.error(f"Failed to wire lifecycle callbacks for {node.name}: {e}")

    # FIX #6: Reconcile initial state from orchestrator
    if reconcile_on_create:
        try:
            reconciler = StateReconciler(orchestrator)
            reconciler.reconcile(link)
        except Exception as e:
            logger.debug(f"State reconciliation skipped for {node.name}: {e}")

    return link


def wire_all_callbacks(
    orchestrator: CommandOrchestrator,
    hierarchy: list[CommandNode],
    keyboard_config,
) -> dict[str, CmdorcCommandLink]:
    """Wire callbacks for all commands in the hierarchy.

    Useful for embedding - creates all links with callbacks.

    Args:
        orchestrator: CommandOrchestrator
        hierarchy: List of CommandNode roots
        keyboard_config: KeyboardConfig with shortcuts

    Returns:
        Dict mapping command name to CmdorcCommandLink
    """
    links = {}

    def walk_tree(nodes):
        for node in nodes:
            shortcut = (
                keyboard_config.shortcuts.get(node.name)
                if keyboard_config.enabled
                else None
            )
            link = create_command_link(
                node,
                orchestrator,
                keyboard_shortcut=shortcut,
                reconcile_on_create=True,
            )
            links[node.name] = link

            if node.children:
                walk_tree(node.children)

    walk_tree(hierarchy)
    return links
