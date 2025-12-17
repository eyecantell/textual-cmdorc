"""cmdorc-frontend: Shared models and utilities for cmdorc frontends."""

__version__ = "0.1.0"

# Models
# Config
from cmdorc_frontend.config import load_frontend_config
from cmdorc_frontend.models import (
    VALID_KEYS,
    CommandNode,
    ConfigValidationResult,
    KeyboardConfig,
    PresentationUpdate,
    TriggerSource,
    map_run_state_to_icon,
)

# State management
from cmdorc_frontend.state_manager import CommandView, StateReconciler

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
