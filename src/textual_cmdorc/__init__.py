"""textual-cmdorc: Embeddable TUI frontend for cmdorc command orchestration."""

__version__ = "0.1.0"

# Public API - Embeddable components
from textual_cmdorc.app import CmdorcApp, HelpScreen
from textual_cmdorc.controller import CmdorcController

# For advanced usage
from textual_cmdorc.integrator import create_command_link, wire_all_callbacks

# Keyboard integration
from textual_cmdorc.keyboard_handler import DuplicateIndicator, KeyboardHandler
from textual_cmdorc.view import CmdorcView
from textual_cmdorc.widgets import CmdorcCommandLink

__all__ = [
    "__version__",
    # Core embeddable components
    "CmdorcController",
    "CmdorcView",
    "CmdorcApp",
    # Keyboard
    "KeyboardHandler",
    "DuplicateIndicator",
    "HelpScreen",
    # Advanced
    "create_command_link",
    "wire_all_callbacks",
    "CmdorcCommandLink",
]
