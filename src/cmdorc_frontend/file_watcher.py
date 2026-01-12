"""File watcher implementation using watchdog for SimpleApp."""

import asyncio
import logging
from pathlib import Path
from threading import Timer

from cmdorc import CommandOrchestrator
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from cmdorc_frontend.watchers import WatcherConfig

logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """Debounced file system event handler."""

    def __init__(
        self,
        trigger_name: str,
        orchestrator: CommandOrchestrator,
        loop: asyncio.AbstractEventLoop,
        manager: "FileWatcherManager",
        debounce_ms: int,
        extensions: list[str] | None = None,
        ignore_dirs: list[str] | None = None,
    ):
        """Initialize handler.

        Args:
            trigger_name: Name of trigger to fire
            orchestrator: CommandOrchestrator instance
            loop: Event loop for scheduling
            manager: FileWatcherManager instance (to check enabled state)
            debounce_ms: Debounce delay in milliseconds
            extensions: Optional file extensions to match (e.g., [".py", ".txt"])
            ignore_dirs: Optional directory names to ignore
        """
        self.trigger_name = trigger_name
        self.orchestrator = orchestrator
        self.loop = loop
        self.manager = manager
        self.debounce_ms = debounce_ms
        self.extensions = extensions
        self.ignore_dirs = ignore_dirs or []
        self._timer: Timer | None = None
        self._last_trigger_time: float = 0.0
        self._pending_file: Path | None = None  # File that will trigger next

    def _matches_filters(self, path: Path) -> bool:
        """Check if path matches configured filters.

        Args:
            path: Path to check

        Returns:
            True if path matches filters
        """
        logger.debug(f"Checking filters for: {path}")

        # Check if path is in ignored directory
        if self.ignore_dirs:
            for part in path.parts:
                if part in self.ignore_dirs:
                    logger.debug(f"  ❌ Ignored dir: {part} in {path.parts}")
                    return False
            logger.debug("  ✓ Ignore dirs check: PASS")

        # Check extensions if specified
        if self.extensions:
            if path.suffix not in self.extensions:
                logger.debug(f"  ❌ Extension check: {path.suffix} not in {self.extensions}")
                return False
            logger.debug(f"  ✓ Extension check: PASS ({path.suffix})")

        # Pattern matching REMOVED - using extensions only

        logger.debug(f"  ✅ All filters PASSED for {path}")
        return True

    def _schedule_trigger(self) -> None:
        """Schedule trigger after debounce delay."""
        # Cancel existing timer
        if self._timer:
            self._timer.cancel()

        # Schedule new trigger
        def fire_trigger():
            """Fire trigger on event loop (only if manager is enabled and not in cooldown)."""
            import time

            now = time.time()

            # Cooldown check: skip if we triggered too recently
            if now - self._last_trigger_time < self.debounce_ms / 1000.0:
                logger.debug(f"Skipping trigger '{self.trigger_name}' - within cooldown period")
                return

            # Check if watchers are enabled before triggering
            if not self.manager.is_enabled():
                logger.debug(f"Skipping trigger '{self.trigger_name}' - watchers disabled")
                return

            try:
                self._last_trigger_time = now  # Update BEFORE triggering
                # Record the triggered file in the manager
                if self._pending_file:
                    self.manager._set_last_triggered_file(self._pending_file, now)
                self.loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.orchestrator.trigger(self.trigger_name))
                )
                logger.debug(f"Triggered '{self.trigger_name}' from file change: {self._pending_file}")
            except Exception as e:
                logger.error(f"Failed to trigger '{self.trigger_name}': {e}")

        self._timer = Timer(self.debounce_ms / 1000.0, fire_trigger)
        self._timer.start()

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle all file system events with unified debouncing.

        Uses on_any_event instead of separate on_modified/on_created to ensure
        all event types flow through the same debounce timer.
        """
        # Skip directory events
        if event.is_directory:
            return

        # Only process created and modified events
        if event.event_type not in ("created", "modified"):
            return

        path = Path(event.src_path)
        if self._matches_filters(path):
            logger.debug(f"File event ({event.event_type}): {path}")
            self._pending_file = path  # Track which file will trigger
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
        self.observer = PollingObserver(timeout=1.0)
        self.handlers: list[_DebouncedHandler] = []
        self._enabled = True  # Controls whether triggers fire
        self._last_triggered_file: Path | None = None
        self._last_triggered_time: float | None = None

    def _discover_directories(self, root: Path, ignore_dirs: list[str] | None) -> list[Path]:
        """Recursively discover all subdirectories, respecting ignore_dirs.

        Args:
            root: Root directory to start discovery
            ignore_dirs: Directory names to skip

        Returns:
            List of all discoverable directories (including root)
        """
        directories = [root]
        ignore_set = set(ignore_dirs or [])

        def should_ignore(path: Path) -> bool:
            """Check if directory should be ignored."""
            # Check each part of the path relative to root
            try:
                rel_path = path.relative_to(root)
                # Check if any component of the relative path is in ignore_set
                for part in rel_path.parts:
                    if part in ignore_set:
                        return True
            except ValueError:
                # path is not relative to root
                pass
            return False

        try:
            for item in root.rglob("*"):
                if not item.is_dir():
                    continue

                # Skip if this directory or any parent should be ignored
                if should_ignore(item):
                    logger.debug(f"Skipping ignored directory: {item}")
                    continue

                directories.append(item)

        except PermissionError as e:
            logger.warning(f"Permission denied accessing {root}: {e}")

        logger.debug(f"Discovered {len(directories)} directories after filtering")
        return directories

    def add_watch(self, config: WatcherConfig) -> None:
        """Add a file watcher.

        Args:
            config: Watcher configuration
        """
        if not config.dir.exists():
            logger.warning(f"Watcher directory does not exist: {config.dir}")
            return

        # Discover directories to watch
        if config.recursive:
            directories = self._discover_directories(config.dir, config.ignore_dirs)
            logger.info(f"Discovered {len(directories)} directories to watch (recursive mode)")
            logger.debug(f"Watching directories: {[str(d) for d in directories]}")
        else:
            directories = [config.dir]
            logger.info("Watching single directory (non-recursive mode)")

        # Create one handler for all directories (shared trigger)
        handler = _DebouncedHandler(
            trigger_name=config.trigger_emitted,
            orchestrator=self.orchestrator,
            loop=self.loop,
            manager=self,
            debounce_ms=config.debounce_ms,
            extensions=config.extensions,
            ignore_dirs=config.ignore_dirs,
        )

        # Schedule watch for each directory (recursive=False for each)
        for directory in directories:
            watch_path = str(directory)
            self.observer.schedule(handler, watch_path, recursive=False)
            logger.debug(f"Scheduled watch: {watch_path} (recursive=False)")

        self.handlers.append(handler)

        logger.info(
            f"Watching '{config.trigger_emitted}' - "
            f"{len(directories)} dir(s), "
            f"extensions: {config.extensions}, "
            f"debounce: {config.debounce_ms}ms"
        )
        logger.debug(
            f"Watch config - Recursive: {config.recursive}, "
            f"Extensions: {config.extensions}, Ignore: {config.ignore_dirs}"
        )

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

    def enable(self) -> None:
        """Enable file watcher triggers.

        File events will continue to be detected, but triggers will now fire.
        """
        if not self._enabled:
            self._enabled = True
            logger.info("File watcher triggers enabled")

    def disable(self) -> None:
        """Disable file watcher triggers.

        File events will still be detected, but triggers will not fire.
        """
        if self._enabled:
            self._enabled = False
            logger.info("File watcher triggers disabled")

    def is_enabled(self) -> bool:
        """Check if file watcher triggers are enabled.

        Returns:
            True if triggers are enabled, False otherwise.
        """
        return self._enabled

    def _set_last_triggered_file(self, file_path: Path, timestamp: float) -> None:
        """Set the last triggered file (called by handlers).

        Args:
            file_path: Path to the file that triggered
            timestamp: Time when the trigger fired
        """
        self._last_triggered_file = file_path
        self._last_triggered_time = timestamp

    def get_last_triggered_file(self) -> tuple[Path | None, float | None]:
        """Get the last file that triggered a watcher.

        Returns:
            Tuple of (file_path, timestamp) or (None, None) if no triggers yet.
        """
        return self._last_triggered_file, self._last_triggered_time
