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

    def format_chain(self, separator: str = " → ", max_width: int = 80) -> str:
        """Format trigger chain for display, with optional left truncation.

        Args:
            separator: String to join trigger events with.
            max_width: Maximum width before truncation (default 80).
                      If exceeded, truncates from left with "..." prefix.
                      FIX #7: Minimum width check (10 chars) prevents negative keep_chars.

        Returns:
            Formatted string representation of the chain, possibly truncated.
        """
        if not self.chain:
            return "manual"

        full_chain = separator.join(self.chain)

        # FIX #7: Minimum width check before truncation
        if max_width < 10:
            # Too narrow to truncate meaningfully, return as-is
            return full_chain

        # Truncate from left if needed
        if len(full_chain) > max_width:
            keep_chars = max_width - 4  # Reserve 4 for "... "
            if keep_chars > 0:
                return f"...{separator}{full_chain[-keep_chars:]}"

        return full_chain

    def get_semantic_summary(self) -> str:
        """Get human-readable summary of trigger source.

        Returns:
            Short semantic description:
            - "Ran manually" (no chain)
            - "Ran automatically (file change)" (file watcher)
            - "Ran automatically (triggered by another command)" (lifecycle)
        """
        if not self.chain:
            return "Ran manually"

        if self.kind == "file":
            return "Ran automatically (file change)"
        elif self.kind == "lifecycle":
            return "Ran automatically (triggered by another command)"
        else:
            return "Ran automatically"


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


@dataclass
class ConfigValidationResult:
    """Results from startup configuration validation.

    RECOMMENDATION #3: Built by controller, consumed by app for display only.
    """

    commands_loaded: int = 0
    """Number of commands successfully loaded."""

    watchers_active: int = 0
    """Number of file watchers started."""

    warnings: list[str] = field(default_factory=list)
    """Config issues found (non-fatal)."""

    errors: list[str] = field(default_factory=list)
    """Config errors (should be fatal)."""


@dataclass
class KeyboardConfig:
    """Keyboard shortcut configuration.

    FIX #8: Shortcuts validated against VALID_KEYS set (1-9, a-z, f1-f12).
    """

    shortcuts: dict[str, str]
    """Mapping of command_name -> key."""

    enabled: bool = True
    """Whether keyboard shortcuts are enabled."""

    show_in_tooltips: bool = True
    """Whether to show keyboard hints in tooltips."""


# FIX #8: Valid keyboard keys
VALID_KEYS = set(
    [str(i) for i in range(1, 10)]  # 1-9
    + [chr(i) for i in range(ord("a"), ord("z") + 1)]  # a-z
    + [f"f{i}" for i in range(1, 13)]  # f1-f12
)


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
