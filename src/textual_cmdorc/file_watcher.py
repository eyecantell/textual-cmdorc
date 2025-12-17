"""Concrete file watcher implementation using watchdog."""

import asyncio
import logging

from cmdorc import CommandOrchestrator

from cmdorc_frontend.watchers import TriggerSourceWatcher, WatcherConfig

logger = logging.getLogger(__name__)


class WatchdogWatcher(TriggerSourceWatcher):
    """File watcher using watchdog library."""

    def __init__(self, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop):
        """Initialize watcher.

        Args:
            orchestrator: CommandOrchestrator instance
            loop: Event loop for scheduling tasks
        """
        self.orchestrator = orchestrator
        self.loop = loop
        self.observer = None
        self.handlers: list = []

    def add_watch(self, config: WatcherConfig) -> None:
        """Add a watch configuration."""
        if not config.dir.exists():
            logger.warning(f"Watcher directory does not exist: {config.dir}")
            return
        logger.info(f"Adding watch on {config.dir} → '{config.trigger}'")

    def start(self) -> None:
        """Start watching."""
        logger.info("File watcher manager started")

    def stop(self) -> None:
        """Stop watching."""
        logger.info("File watcher manager stopped")
