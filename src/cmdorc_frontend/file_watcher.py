"""File watcher implementation using watchdog for SimpleApp."""

import asyncio
import logging
from pathlib import Path
from threading import Timer

from cmdorc import CommandOrchestrator
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from cmdorc_frontend.watchers import WatcherConfig

logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """Debounced file system event handler."""

    def __init__(
        self,
        trigger_name: str,
        orchestrator: CommandOrchestrator,
        loop: asyncio.AbstractEventLoop,
        debounce_ms: int,
        patterns: list[str] | None = None,
        extensions: list[str] | None = None,
    ):
        """Initialize handler.

        Args:
            trigger_name: Name of trigger to fire
            orchestrator: CommandOrchestrator instance
            loop: Event loop for scheduling
            debounce_ms: Debounce delay in milliseconds
            patterns: Optional glob patterns to match
            extensions: Optional extensions to match
        """
        self.trigger_name = trigger_name
        self.orchestrator = orchestrator
        self.loop = loop
        self.debounce_ms = debounce_ms
        self.patterns = patterns
        self.extensions = extensions
        self._timer: Timer | None = None

    def _matches_filters(self, path: Path) -> bool:
        """Check if path matches configured filters.

        Args:
            path: Path to check

        Returns:
            True if path matches filters
        """
        # Check extensions if specified
        if self.extensions and path.suffix not in self.extensions:
            return False

        # Check patterns if specified (simple suffix matching)
        if self.patterns:
            matched = False
            for pattern in self.patterns:
                # Simple pattern matching - just check if path ends with pattern suffix
                if pattern.startswith("**/*"):
                    suffix = pattern[4:]  # Remove "**/*"
                    if path.name.endswith(suffix):
                        matched = True
                        break
                elif pattern.startswith("*."):
                    if path.suffix == pattern[1:]:
                        matched = True
                        break
            if not matched:
                return False

        return True

    def _schedule_trigger(self) -> None:
        """Schedule trigger after debounce delay."""
        # Cancel existing timer
        if self._timer:
            self._timer.cancel()

        # Schedule new trigger
        def fire_trigger():
            """Fire trigger on event loop."""
            try:
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.orchestrator.trigger(self.trigger_name))
                )
                logger.debug(f"Triggered '{self.trigger_name}' from file change")
            except Exception as e:
                logger.error(f"Failed to trigger '{self.trigger_name}': {e}")

        self._timer = Timer(self.debounce_ms / 1000.0, fire_trigger)
        self._timer.start()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if self._matches_filters(path):
            logger.debug(f"File change detected: {path}")
            self._schedule_trigger()

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if self._matches_filters(path):
            logger.debug(f"File created: {path}")
            self._schedule_trigger()


class FileWatcherManager:
    """Manages file watchers for SimpleApp."""

    def __init__(self, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop):
        """Initialize file watcher manager.

        Args:
            orchestrator: CommandOrchestrator instance
            loop: Event loop for scheduling
        """
        self.orchestrator = orchestrator
        self.loop = loop
        self.observer = Observer()
        self.handlers: list[_DebouncedHandler] = []

    def add_watch(self, config: WatcherConfig) -> None:
        """Add a file watcher.

        Args:
            config: Watcher configuration
        """
        if not config.dir.exists():
            logger.warning(f"Watcher directory does not exist: {config.dir}")
            return

        # Create debounced handler
        handler = _DebouncedHandler(
            trigger_name=config.trigger,
            orchestrator=self.orchestrator,
            loop=self.loop,
            debounce_ms=config.debounce_ms,
            patterns=config.patterns,
            extensions=config.extensions,
        )

        # Schedule watch
        self.observer.schedule(handler, str(config.dir), recursive=True)
        self.handlers.append(handler)

        logger.info(f"Watching {config.dir} for '{config.trigger}' (debounce: {config.debounce_ms}ms)")

    def start(self) -> None:
        """Start all file watchers."""
        if not self.handlers:
            logger.debug("No file watchers configured")
            return

        self.observer.start()
        logger.info(f"Started {len(self.handlers)} file watcher(s)")

    def stop(self) -> None:
        """Stop all file watchers."""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=2.0)
            logger.info("Stopped file watchers")

        # Cancel pending timers
        for handler in self.handlers:
            if handler._timer:
                handler._timer.cancel()
