"""Keyboard handler for safe, conflict-aware keyboard binding.

Provides sync-safe keyboard binding that respects FIX #1 and FIX #3:
- FIX #1: Uses controller.request_run() for sync-safe command execution
- FIX #3: Detects and warns about keyboard conflicts
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class KeyboardHandler:
    """Safe keyboard handler with conflict detection and sync-safe binding.

    Features:
    - Detects keyboard conflicts (multiple commands on same key)
    - Provides sync-safe callbacks using controller.request_run()
    - Tracks bindings for help screen display
    - Warns about shadowed commands (first one wins)
    """

    def __init__(self, controller, app=None):
        """Initialize keyboard handler.

        Args:
            controller: CmdorcController instance
            app: Optional Textual App for binding (if not provided, returns callbacks)
        """
        self.controller = controller
        self.app = app
        self.bindings = {}  # Track active bindings
        self.callbacks = {}  # Track callbacks for testing

    def bind_all(self) -> dict[str, Callable]:
        """Bind all configured keyboard shortcuts and return callbacks.

        Returns dict mapping key -> callback for testing or manual binding.

        Returns:
            Dict[str, Callable] mapping key to sync-safe callback
        """
        callbacks = {}
        keyboard_hints = self.controller.keyboard_hints
        conflicts = self.controller.keyboard_conflicts

        for key, command_name in keyboard_hints.items():
            # Create sync-safe callback (FIX #1)
            callback = self._create_callback(command_name)
            callbacks[key] = callback

            # Track binding
            self.bindings[key] = command_name
            self.callbacks[key] = callback

            # Warn about conflicts (FIX #3)
            if key in conflicts:
                conflicting_commands = conflicts[key]
                logger.warning(
                    f"Keyboard conflict on [{key}]: {conflicting_commands}. "
                    f"Only {command_name} will execute (first one wins)"
                )

            # Try to bind in app if available
            if self.app:
                try:
                    # Note: action parameters must be quoted strings for Textual to parse correctly
                    self.app.bind(key, f'command("{command_name}")', show=True)
                except Exception as e:
                    logger.error(f"Failed to bind key [{key}]: {e}")

        return callbacks

    def _create_callback(self, command_name: str) -> Callable:
        """Create sync-safe callback for command.

        FIX #1: Uses controller.request_run() for sync-safe execution.

        Args:
            command_name: Name of command to execute

        Returns:
            Callable that executes command safely
        """

        def callback():
            """Sync-safe command execution callback."""
            try:
                self.controller.request_run(command_name)
            except Exception as e:
                logger.error(f"Error executing {command_name}: {e}")

        return callback

    def get_binding_help(self) -> str:
        """Get formatted help text for keyboard bindings.

        Returns:
            Formatted string showing all bindings and conflicts
        """
        help_text = "Keyboard Shortcuts:\n"

        if not self.bindings:
            help_text += "  (none configured)\n"
            return help_text

        conflicts = self.controller.keyboard_conflicts

        for key, command in sorted(self.bindings.items()):
            # Mark conflicts
            if key in conflicts:
                conflicting = conflicts[key]
                help_text += f"  [{key}] → {command} ⚠ (also: {', '.join(conflicting[1:])})\n"
            else:
                help_text += f"  [{key}] → {command}\n"

        return help_text

    def validate_bindings(self) -> dict[str, list[str]]:
        """Validate all bindings and return issues.

        Returns:
            Dict with 'conflicts' and 'shadowed' keys listing problems
        """
        conflicts = self.controller.keyboard_conflicts
        shadowed = {}

        for key, commands in conflicts.items():
            if len(commands) > 1:
                shadowed[key] = commands[1:]  # All but first are shadowed

        return {
            "conflicts": conflicts,
            "shadowed": shadowed,
        }


class DuplicateIndicator:
    """Visual indicator for duplicate commands in the tree.

    Shows which commands appear multiple times in the hierarchy.
    """

    DUPLICATE_MARKER = "↳"  # Visual indicator

    @staticmethod
    def format_name(name: str, is_duplicate: bool) -> str:
        """Format command name with duplicate indicator.

        Args:
            name: Command name
            is_duplicate: Whether this is a duplicate

        Returns:
            Formatted name with optional indicator
        """
        if is_duplicate:
            return f"{name} {DuplicateIndicator.DUPLICATE_MARKER}"
        return name

    @staticmethod
    def get_duplicate_warning(name: str, count: int) -> str:
        """Get warning message for duplicate command.

        Args:
            name: Command name
            count: Number of occurrences

        Returns:
            Warning message
        """
        if count <= 1:
            return ""

        return (
            f"⚠ Command '{name}' appears {count} times in the hierarchy. "
            f"Shortcuts and cancellations affect all instances."
        )
