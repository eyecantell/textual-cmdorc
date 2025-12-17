"""cmdorc-frontend: Shared models and utilities for cmdorc frontends."""

__version__ = "0.1.0"

# Models
from cmdorc_frontend.models import (
    CommandNode,
    TriggerSource,
    PresentationUpdate,
    ConfigValidationResult,
    KeyboardConfig,
    VALID_KEYS,
    map_run_state_to_icon,
)

# State management
from cmdorc_frontend.state_manager import StateReconciler, CommandView

# Config
from cmdorc_frontend.config import load_frontend_config

__all__ = [
    "__version__",
    # Models
    "CommandNode",
    "TriggerSource",
    "PresentationUpdate",
    "ConfigValidationResult",
    "KeyboardConfig",
    "VALID_KEYS",
    "map_run_state_to_icon",
    # State
    "StateReconciler",
    "CommandView",
    # Config
    "load_frontend_config",
]
