"""
Reusable frontend adapter for CommandOrchestrator.

Provides a clean, frontend-agnostic interface for:
- Loading and validating configurations
- Executing commands (run/cancel)
- Wiring lifecycle callbacks with correct signatures
- Querying command status

This adapter can be used by any frontend (TUI, VSCode, web, etc.)
without depending on Textual or any UI framework.
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from cmdorc import CommandOrchestrator, RunHandle, load_config

from cmdorc_frontend.config import load_frontend_config

logger = logging.getLogger(__name__)

# Optional: Only import if watchdog is available
try:
    from cmdorc_frontend.file_watcher import FileWatcherManager

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    logger.debug("watchdog not available - file watching disabled")


class OrchestratorAdapter:
    """Frontend-agnostic adapter for CommandOrchestrator.

    Handles:
    - Configuration loading and validation
    - Command execution (run/cancel)
    - Lifecycle callback wiring (with correct signatures)
    - Keyboard configuration

    Usage (Embedded):
        adapter = OrchestratorAdapter(config_path)
        loop = asyncio.get_running_loop()
        adapter.attach(loop)

        # Wire callbacks
        adapter.on_command_success("MyCommand", lambda handle: ...)
        adapter.on_command_failed("MyCommand", lambda handle: ...)

        # Execute
        await adapter.run_command("MyCommand")
        adapter.detach()
    """

    def __init__(self, config_path: str | Path, enable_watchers: bool = True):
        """Initialize adapter with configuration.

        Args:
            config_path: Path to TOML config file
            enable_watchers: Whether to enable file watchers (default: True)
        """
        self.config_path = Path(config_path)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._enable_watchers = enable_watchers

        # Load configuration
        runner_config = load_config(self.config_path)
        self.orchestrator = CommandOrchestrator(runner_config)

        # Load frontend configuration
        _, self.keyboard_config, self._watchers, self._hierarchy = load_frontend_config(self.config_path)

        # Track state
        self._is_attached = False
        self._watcher_manager: FileWatcherManager | None = None
        self._command_success_callbacks: dict[str, list[Callable]] = {}
        self._command_failed_callbacks: dict[str, list[Callable]] = {}
        self._command_cancelled_callbacks: dict[str, list[Callable]] = {}

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach adapter to an event loop.

        Must be called before executing commands. Should be called from
        within an async context (e.g., on_mount()).

        Args:
            loop: Event loop to attach to

        Raises:
            RuntimeError: If already attached or loop is not running
        """
        if self._is_attached:
            logger.warning("Adapter already attached to event loop")
            return

        if not loop.is_running():
            raise RuntimeError("Event loop must be running to attach")

        self._loop = loop
        self._is_attached = True

        # Wire all registered lifecycle callbacks
        for cmd_name in self.orchestrator.list_commands():
            self._wire_lifecycle_callbacks(cmd_name)

        # Start file watchers if enabled
        if self._enable_watchers and self._watchers and _WATCHDOG_AVAILABLE:
            try:
                self._watcher_manager = FileWatcherManager(self.orchestrator, loop)
                for watcher_config in self._watchers:
                    self._watcher_manager.add_watch(watcher_config)
                self._watcher_manager.start()
            except Exception as e:
                logger.error(f"Failed to start file watchers: {e}")
                self._watcher_manager = None

        logger.debug("Adapter attached to event loop")

    def detach(self) -> None:
        """Detach adapter from event loop.

        Should be called during cleanup (e.g., on_unmount()).
        """
        # Stop file watchers
        if self._watcher_manager:
            try:
                self._watcher_manager.stop()
            except Exception as e:
                logger.error(f"Failed to stop file watchers: {e}")
            self._watcher_manager = None

        self._is_attached = False
        self._loop = None
        logger.debug("Adapter detached from event loop")

    def _wire_lifecycle_callbacks(self, command_name: str) -> None:
        """Wire all registered callbacks for a command to orchestrator.

        Maps callback registrations to orchestrator.set_lifecycle_callback()
        with correct parameter names:
        - on_success (not on_started)
        - on_failed
        - on_cancelled

        Args:
            command_name: Command to wire callbacks for
        """
        on_success = self._make_callback_handler(command_name, "success")
        on_failed = self._make_callback_handler(command_name, "failed")
        on_cancelled = self._make_callback_handler(command_name, "cancelled")

        # Use correct parameter names (fixes integrator.py bug)
        self.orchestrator.set_lifecycle_callback(
            command_name,
            on_success=on_success,
            on_failed=on_failed,
            on_cancelled=on_cancelled,
        )

    def _make_callback_handler(self, command_name: str, status: str) -> Callable:
        """Create a callback handler that dispatches to registered listeners.

        Args:
            command_name: Command name
            status: One of "success", "failed", "cancelled"

        Returns:
            Callable that takes (handle, context) and dispatches to listeners
        """

        def handler(handle: RunHandle | None, context=None):
            callbacks_map = {
                "success": self._command_success_callbacks,
                "failed": self._command_failed_callbacks,
                "cancelled": self._command_cancelled_callbacks,
            }

            callbacks = callbacks_map.get(status, {})
            for callback in callbacks.get(command_name, []):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        # Schedule async callback on the event loop
                        if self._loop and self._loop.is_running():
                            asyncio.create_task(callback(handle))
                    else:
                        callback(handle)
                except Exception as e:
                    logger.exception(f"Error in {status} callback for '{command_name}': {e}")

        return handler

    # ========================================================================
    # Command Execution
    # ========================================================================

    async def run_command(self, name: str, vars: dict[str, str] | None = None) -> RunHandle:
        """Execute a command asynchronously.

        Args:
            name: Command name
            vars: Optional variable overrides

        Returns:
            RunHandle for the started run

        Raises:
            RuntimeError: If not attached
        """
        if not self._is_attached or not self._loop:
            raise RuntimeError("Adapter not attached - call attach(loop) first")

        return await self.orchestrator.run_command(name, vars)

    def request_run(self, name: str) -> None:
        """Request command execution (sync-safe from UI callbacks).

        Schedules the command on the attached event loop without blocking.
        Safe to call from Textual message handlers.

        Args:
            name: Command name

        Raises:
            RuntimeError: If not attached
        """
        if not self._is_attached or not self._loop:
            raise RuntimeError("Adapter not attached - call attach(loop) first")

        async def run():
            try:
                await self.run_command(name)
            except Exception as e:
                logger.error(f"Failed to run command '{name}': {e}")

        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(run()))

    async def cancel_command(self, name: str) -> int:
        """Cancel all active runs of a command.

        Args:
            name: Command name

        Returns:
            Number of runs cancelled
        """
        if not self._is_attached or not self._loop:
            raise RuntimeError("Adapter not attached - call attach(loop) first")

        return await self.orchestrator.cancel_command(name)

    def request_cancel(self, name: str) -> None:
        """Request command cancellation (sync-safe from UI callbacks).

        Args:
            name: Command name

        Raises:
            RuntimeError: If not attached
        """
        if not self._is_attached or not self._loop:
            raise RuntimeError("Adapter not attached - call attach(loop) first")

        async def cancel():
            try:
                await self.cancel_command(name)
            except Exception as e:
                logger.error(f"Failed to cancel command '{name}': {e}")

        self._loop.call_soon_threadsafe(lambda: asyncio.create_task(cancel()))

    # ========================================================================
    # Callback Registration
    # ========================================================================

    def on_command_success(self, name: str, callback: Callable[[RunHandle], None]) -> None:
        """Register callback for successful command completion.

        Args:
            name: Command name
            callback: Callable(handle) - may be async
        """
        if name not in self._command_success_callbacks:
            self._command_success_callbacks[name] = []
        self._command_success_callbacks[name].append(callback)

        # Re-wire if already attached
        if self._is_attached:
            self._wire_lifecycle_callbacks(name)

    def on_command_failed(self, name: str, callback: Callable[[RunHandle], None]) -> None:
        """Register callback for failed command.

        Args:
            name: Command name
            callback: Callable(handle) - may be async
        """
        if name not in self._command_failed_callbacks:
            self._command_failed_callbacks[name] = []
        self._command_failed_callbacks[name].append(callback)

        # Re-wire if already attached
        if self._is_attached:
            self._wire_lifecycle_callbacks(name)

    def on_command_cancelled(self, name: str, callback: Callable[[RunHandle], None]) -> None:
        """Register callback for cancelled command.

        Args:
            name: Command name
            callback: Callable(handle) - may be async
        """
        if name not in self._command_cancelled_callbacks:
            self._command_cancelled_callbacks[name] = []
        self._command_cancelled_callbacks[name].append(callback)

        # Re-wire if already attached
        if self._is_attached:
            self._wire_lifecycle_callbacks(name)

    # ========================================================================
    # Queries
    # ========================================================================

    def get_keyboard_shortcuts(self) -> dict[str, str]:
        """Get keyboard shortcut mapping.

        Returns:
            Dict mapping command_name -> shortcut key
        """
        return self.keyboard_config.shortcuts.copy() if self.keyboard_config.shortcuts else {}

    def get_command_names(self) -> list[str]:
        """Get all registered command names in TOML order.

        Returns:
            List of command names in the order they appear in config
        """
        return self.orchestrator.list_commands()
