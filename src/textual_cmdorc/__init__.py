"""textual-cmdorc: Embeddable TUI frontend for cmdorc command orchestration."""

__version__ = "0.1.0"

# Public API
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter
from textual_cmdorc.cmdorc_app import CmdorcApp, CmdorcWidget
from textual_cmdorc.logging import (
    disable_logging,
    get_log_file_path,
    get_logger,
    setup_logging,
)
from textual_cmdorc.watcher_status_line import WatcherStatusLine

__all__ = [
    "__version__",
    # Primary components
    "CmdorcApp",  # Standalone app with Header/Footer
    "CmdorcWidget",  # Composable widget for embedding
    "OrchestratorAdapter",  # Framework-agnostic backend
    "WatcherStatusLine",  # File watcher status widget
    # Logging utilities
    "setup_logging",
    "disable_logging",
    "get_logger",
    "get_log_file_path",
]
