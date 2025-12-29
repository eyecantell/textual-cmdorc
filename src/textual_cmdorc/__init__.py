"""textual-cmdorc: Embeddable TUI frontend for cmdorc command orchestration."""

__version__ = "0.1.0"

# Public API
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter
from textual_cmdorc.cmdorc_app import CmdorcApp, CmdorcWidget

__all__ = [
    "__version__",
    # Primary components
    "CmdorcApp",  # Standalone app with Header/Footer
    "CmdorcWidget",  # Composable widget for embedding
    "OrchestratorAdapter",  # Framework-agnostic backend
]
