"""Pluggable notification protocol for cmdorc_frontend.

Allows controller to decouple from logging implementation.
Can be replaced with custom handlers for testing, embedding, or UI integration.
"""

import logging
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


class NoOpNotifier:
    """POLISH #3: Silent no-op notifier - default for embedded mode.

    Prevents unwanted stderr spam when controller is embedded without a view/log pane.
    """

    def info(self, msg: str) -> None:
        """Do nothing."""
        pass

    def warning(self, msg: str) -> None:
        """Do nothing."""
        pass

    def error(self, msg: str) -> None:
        """Do nothing."""
        pass


class LoggingNotifier:
    """Implementation using stdlib logging - for debugging/development."""

    def info(self, msg: str) -> None:
        logging.info(msg)

    def warning(self, msg: str) -> None:
        logging.warning(msg)

    def error(self, msg: str) -> None:
        logging.error(msg)
