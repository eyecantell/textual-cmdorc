"""textual-cmdorc: Embeddable TUI frontend for cmdorc command orchestration."""

__version__ = "0.1.0"

# Public API - Simplified architecture (Phase 7+)
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter
from textual_cmdorc.simple_app import SimpleApp

__all__ = [
    "__version__",
    # Primary components
    "SimpleApp",
    "OrchestratorAdapter",
]
