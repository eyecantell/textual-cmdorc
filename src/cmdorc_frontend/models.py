"""Shared data models for cmdorc_frontend."""

from dataclasses import dataclass, field
from typing import Literal
from pathlib import Path

try:
    from cmdorc import RunState, CommandConfig
except ImportError:
    # Fallback for testing without cmdorc installed
    RunState = None
    CommandConfig = None


@dataclass
class TriggerSource:
    """Represents the trigger chain that caused a command to run."""

    name: str
    """The name of the last trigger in the chain (for backward compatibility)."""

    kind: Literal["manual", "file", "lifecycle"]
    """The kind of the last trigger: manual, file, or lifecycle."""

    chain: list[str] = field(default_factory=list)
    """Full trigger chain - ordered list of all events leading to this command."""

    @classmethod
    def from_trigger_chain(cls, trigger_chain: list[str]) -> "TriggerSource":
        """Create TriggerSource from cmdorc's RunHandle.trigger_chain.

        Args:
            trigger_chain: Ordered list of trigger events from cmdorc.

        Returns:
            TriggerSource with name set to last trigger and kind inferred.
        """
        if not trigger_chain:
            return cls(name="manual", kind="manual", chain=[])

        last_trigger = trigger_chain[-1]

        # Determine kind from last trigger
        if last_trigger.startswith("command_"):
            kind = "lifecycle"
        elif "file" in last_trigger.lower():
            kind = "file"
        else:
            kind = "manual"

        return cls(name=last_trigger, kind=kind, chain=trigger_chain)

    def format_chain(self, separator: str = " → ", max_width: int | None = None) -> str:
        """Format trigger chain for display, with optional left truncation.

        Args:
            separator: String to join trigger events with.
            max_width: Maximum width before truncation (default None = no limit).
                      If exceeded, truncates from left with "..." prefix.

        Returns:
            Formatted string representation of the chain, possibly truncated.
        """
        if not self.chain:
            return "manual"

        full_chain = separator.join(self.chain)

        # Truncate from left if needed
        if max_width is not None and len(full_chain) > max_width:
            keep_chars = max_width - 4  # Reserve 4 for "... "
            if keep_chars > 0:
                return f"...{separator}{full_chain[-keep_chars:]}"

        return full_chain


@dataclass
class PresentationUpdate:
    """Update to be applied to a widget display."""

    icon: str
    """Status icon to display."""

    running: bool
    """Whether the command is currently running."""

    tooltip: str
    """Tooltip text for the widget."""

    output_path: Path | None = None
    """Path to output file (if available)."""


@dataclass
class CommandNode:
    """Hierarchical node representing a command and its children."""

    config: CommandConfig
    """Command configuration from cmdorc."""

    children: list["CommandNode"] = field(default_factory=list)
    """Child commands (those triggered by this command's success/failure/cancellation)."""

    @property
    def name(self) -> str:
        """Get command name from config."""
        return self.config.name

    @property
    def triggers(self) -> list[str]:
        """Get triggers from config."""
        return self.config.triggers


def map_run_state_to_icon(state: "RunState") -> str:
    """Map cmdorc.RunState enum to UI icons.

    Args:
        state: RunState from cmdorc.

    Returns:
        Unicode icon string representing the state.
    """
    if RunState is None:
        return "❓"

    if state == RunState.SUCCESS:
        return "✅"
    elif state == RunState.FAILED:
        return "❌"
    elif state == RunState.CANCELLED:
        return "⏹"
    elif state == RunState.RUNNING:
        return "⏳"
    else:
        return "❓"  # PENDING or unknown state
