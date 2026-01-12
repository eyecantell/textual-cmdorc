"""Pluggable notification protocol for cmdorc_frontend.

Allows controller to decouple from logging implementation.
Can be replaced with custom handlers for testing, embedding, or UI integration.
"""

from typing import Protocol


class CmdorcNotifier(Protocol):
    """Protocol for notifications - host can provide custom implementation."""

    def info(self, message: str) -> None:
        """Informational message."""
        ...

    def warning(self, message: str) -> None:
        """Warning message."""
        ...

    def error(self, message: str) -> None:
        """Error message."""
        ...
