"""Abstract watcher protocol for file watching implementations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class WatcherConfig:
    """Configuration for a file watcher."""

    dir: Path
    """Directory to watch."""

    patterns: list[str] | None = None
    """Include patterns (glob style)."""

    extensions: list[str] | None = None
    """Include extensions (fallback if patterns not specified)."""

    ignore_dirs: list[str] | None = None
    """Directories to ignore."""

    trigger: str = ""
    """Trigger name to fire on file change."""

    debounce_ms: int = 300
    """Debounce delay in milliseconds."""


class TriggerSourceWatcher(Protocol):
    """Protocol for file watcher implementations."""

    def add_watch(self, config: WatcherConfig) -> None:
        """Add a watch configuration."""
        ...

    def start(self) -> None:
        """Start watching."""
        ...

    def stop(self) -> None:
        """Stop watching."""
        ...
