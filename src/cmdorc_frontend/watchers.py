"""Abstract watcher protocol for file watching implementations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class WatcherConfig:
    """Configuration for a file watcher."""

    dir: Path
    """Directory to watch."""

    extensions: list[str] | None = None
    """File extensions to watch (e.g., [".py", ".txt"])."""

    ignore_dirs: list[str] | None = None
    """Directories to ignore."""

    trigger_emitted: str = ""
    """Trigger emitted by this watcher on file change."""

    debounce_ms: int = 300
    """Debounce delay in milliseconds."""

    recursive: bool = True
    """Recursively watch subdirectories (default: True)."""


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
