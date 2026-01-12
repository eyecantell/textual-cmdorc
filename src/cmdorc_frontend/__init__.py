"""cmdorc-frontend: Shared models and utilities for cmdorc frontends."""

__version__ = "0.1.0"

# Models
# Config
from cmdorc_frontend.config import load_frontend_config
from cmdorc_frontend.models import (
    VALID_KEYS,
    CommandNode,
    ConfigValidationResult,
    EditorConfig,
    KeyboardConfig,
    PresentationUpdate,
    TriggerSource,
    map_run_state_to_icon,
)

__all__ = [
    "__version__",
    # Models
    "CommandNode",
    "TriggerSource",
    "PresentationUpdate",
    "ConfigValidationResult",
    "EditorConfig",
    "KeyboardConfig",
    "VALID_KEYS",
    "map_run_state_to_icon",
    # Config
    "load_frontend_config",
]
