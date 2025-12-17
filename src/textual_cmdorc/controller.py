"""Non-Textual controller for cmdorc orchestration. Primary embed point."""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from cmdorc import CommandOrchestrator
from cmdorc_frontend.config import load_frontend_config
from cmdorc_frontend.models import TriggerSource, CommandNode, ConfigValidationResult
from cmdorc_frontend.notifier import CmdorcNotifier, NoOpNotifier
from cmdorc_frontend.watchers import WatcherConfig

logger = logging.getLogger(__name__)


class CmdorcController:
    """Non-Textual controller for orchestration logic. Primary embed point.

    RECOMMENDATION #2: Stable Public API for v0.1
    ============================================
    Stable methods: attach(), detach(), request_run(), request_cancel(),
    run_command(), cancel_command(), keyboard_hints, keyboard_conflicts.
    Internal methods (_on_file_change, etc.) may change.
    """

    def __init__(
        self,
        config_path: str | Path,
        notifier: CmdorcNotifier | None = None,
        enable_watchers: bool = True,
    ):
        """Initialize controller.

        Args:
            config_path: Path to TOML config
            notifier: Optional notification handler (defaults to NoOpNotifier - silent)
            enable_watchers: If True, watchers auto-start on attach(). If False, host controls lifecycle.
        """
        self.config_path = Path(config_path)
        self.notifier = notifier or NoOpNotifier()  # POLISH #3: Silent by default
        self.enable_watchers = enable_watchers
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # FIX #1: Store loop reference
        self._file_watcher = None

        # Load configuration
        try:
            (
                self.runner_config,
                self.keyboard_config,
                self.watcher_configs,
                self.hierarchy,
            ) = load_frontend_config(self.config_path)
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise

        # Initialize orchestrator
        self.orchestrator = CommandOrchestrator(self.runner_config)

        # FIX #3: Cache keyboard conflicts (computed once)
        self._keyboard_conflicts = self._compute_keyboard_conflicts()

        # Outbound events (host wires these)
        self.on_command_started: Callable[[str, TriggerSource], None] | None = None
        self.on_command_finished: Callable[[str, object], None] | None = None
        self.on_validation_result: Callable[[ConfigValidationResult], None] | None = None
        self.on_state_reconciled: Callable[[str, object], None] | None = None  # FIX #6

        # Intent signals
        self.on_quit_requested: Callable[[], None] | None = None
        self.on_cancel_all_requested: Callable[[], None] | None = None

    def _compute_keyboard_conflicts(self) -> dict[str, list[str]]:
        """FIX #3: Compute keyboard conflicts once during init."""
        conflicts = {}
        for cmd_name, key in self.keyboard_config.shortcuts.items():
            if key not in conflicts:
                conflicts[key] = []
            conflicts[key].append(cmd_name)
        # Return only keys with multiple commands
        return {k: v for k, v in conflicts.items() if len(v) > 1}

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach to event loop and start watchers if enabled.

        RECOMMENDATION #1: Idempotent - guards against double-attach and non-running loop.
        FIX #1: Store loop reference for sync-safe task creation.
        """
        # RECOMMENDATION #1: Idempotency guard
        if self._loop is not None:
            return  # Already attached

        # RECOMMENDATION #1: Validate loop is running
        if not loop.is_running():
            raise RuntimeError(
                "Event loop must be running before attach(). "
                "Call attach() from within on_mount() or after loop started."
            )

        self._loop = loop  # FIX #1: Store for request_run/cancel

        if self.enable_watchers and self.watcher_configs:
            try:
                from textual_cmdorc.file_watcher import WatchdogWatcher

                self._file_watcher = WatchdogWatcher(self.orchestrator, loop)
                for cfg in self.watcher_configs:
                    self._file_watcher.add_watch(cfg)
                self._file_watcher.start()
                self.notifier.info(
                    f"File watchers started ({len(self.watcher_configs)} configured)"
                )
            except Exception as e:
                logger.error(f"Failed to start file watchers: {e}")
                self.notifier.error(f"File watcher initialization failed: {e}")

    def detach(self) -> None:
        """Stop watchers and cleanup."""
        if self._file_watcher:
            try:
                self._file_watcher.stop()
            except Exception as e:
                logger.error(f"Error stopping file watcher: {e}")
            self._file_watcher = None
        self._loop = None
        self.notifier.info("File watchers stopped")

    async def run_command(self, name: str) -> None:
        """Run a command by name (async)."""
        if not self.orchestrator.has_command(name):
            self.notifier.warning(f"Command not found: {name}")
            return
        try:
            await self.orchestrator.run_command(name)
            self.notifier.info(f"Started: {name}")
        except Exception as e:
            logger.error(f"Error running command '{name}': {e}")
            self.notifier.error(f"Failed to start {name}: {e}")

    async def cancel_command(self, name: str) -> None:
        """Cancel a running command (async)."""
        if not self.orchestrator.has_command(name):
            self.notifier.warning(f"Command not found: {name}")
            return
        try:
            await self.orchestrator.cancel_command(name)
            self.notifier.info(f"Cancelled: {name}")
        except Exception as e:
            logger.error(f"Error cancelling command '{name}': {e}")
            self.notifier.error(f"Failed to cancel {name}: {e}")

    async def reload_config(self) -> None:
        """Reload configuration from disk."""
        try:
            (
                self.runner_config,
                self.keyboard_config,
                self.watcher_configs,
                self.hierarchy,
            ) = load_frontend_config(self.config_path)
            # FIX #3: Recompute conflicts after reload
            self._keyboard_conflicts = self._compute_keyboard_conflicts()
            self.notifier.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            self.notifier.error(f"Failed to reload config: {e}")

    # FIX #1: Sync-safe helpers for UI integration
    def request_run(self, name: str) -> None:
        """Request command run (sync-safe, schedules async task).

        FIX #1: Uses stored loop reference instead of asyncio.create_task().
        Safe to call from sync contexts (e.g., keyboard event handlers).
        """
        if self._loop is None:
            raise RuntimeError("Controller not attached to event loop. Call attach() first.")
        self._loop.create_task(self.run_command(name))

    def request_cancel(self, name: str) -> None:
        """Request command cancellation (sync-safe, schedules async task).

        FIX #1: Uses stored loop reference instead of asyncio.create_task().
        Safe to call from sync contexts (e.g., keyboard event handlers).
        """
        if self._loop is None:
            raise RuntimeError("Controller not attached to event loop. Call attach() first.")
        self._loop.create_task(self.cancel_command(name))

    # FIX #5: Thread-safe file change handler
    def _on_file_change(self, trigger_name: str) -> None:
        """Handle file change events from watcher thread.

        FIX #5: Uses call_soon_threadsafe to schedule async task from watcher thread.
        """
        if self._loop is None:
            logger.warning(
                f"File change for '{trigger_name}' ignored - controller not attached"
            )
            return
        # FIX #5: Thread-safe task scheduling
        self._loop.call_soon_threadsafe(
            lambda: self._loop.create_task(self.run_command(trigger_name))
        )

    # POLISH #1: Metadata only (no callables)
    @property
    def keyboard_hints(self) -> dict[str, str]:
        """Returns {key: command_name} metadata for host to wire.

        POLISH #1: Returns metadata only (no callables) to decouple host from controller internals.
        Host wires own actions: self.bind(key, lambda: controller.request_run(name))
        """
        return {key: cmd_name for cmd_name, key in self.keyboard_config.shortcuts.items()}

    # FIX #3: Cached keyboard conflicts
    @property
    def keyboard_conflicts(self) -> dict[str, list[str]]:
        """FIX #3: Returns {key: [cmd_name1, cmd_name2, ...]} for keys with multiple commands.

        Cached in __init__() to avoid recomputation on every access.
        """
        return self._keyboard_conflicts

    def validate_config(self) -> ConfigValidationResult:
        """RECOMMENDATION #3: Validate configuration and return structured results.

        App displays results, does not re-derive them.
        """
        result = ConfigValidationResult(
            commands_loaded=len(self.orchestrator.runner_config.commands),
            watchers_active=len(self.watcher_configs) if self.watcher_configs else 0,
        )

        # Keyboard validation
        command_names = {c.name for c in self.orchestrator.runner_config.commands}
        from cmdorc_frontend.models import VALID_KEYS

        for cmd_name, key in self.keyboard_config.shortcuts.items():
            if key not in VALID_KEYS:
                result.warnings.append(
                    f"Invalid key '{key}' for command '{cmd_name}'. "
                    f"Valid keys: 1-9, a-z, f1-f12"
                )

            if cmd_name not in command_names:
                result.warnings.append(f"Shortcut for '{cmd_name}' references unknown command")

        # Keyboard conflicts
        for key, commands in self.keyboard_conflicts.items():
            if len(commands) > 1:
                result.warnings.append(
                    f"Duplicate key '{key}' for {', '.join(commands)} (last one wins)"
                )

        return result
