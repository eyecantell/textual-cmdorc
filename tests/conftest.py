"""Pytest configuration and fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock
from enum import Enum

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Mock cmdorc module before importing our code
class RunState(Enum):
    """Mock RunState enum."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RUNNING = "RUNNING"
    PENDING = "PENDING"


class CommandConfig:
    """Mock CommandConfig."""
    def __init__(self, name="test", command="echo test", triggers=None):
        self.name = name
        self.command = command
        self.triggers = triggers or []


class RunResult:
    """Mock RunResult."""
    def __init__(self, state=RunState.SUCCESS, duration_str="0.1s", output=None):
        self.state = state
        self.duration_str = duration_str
        self.output = output


class RunHandle:
    """Mock RunHandle."""
    def __init__(self, name="test", trigger_chain=None):
        self.name = name
        self.trigger_chain = trigger_chain or []
        self._result = RunResult()
        self.is_finalized = True


class CommandOrchestrator:
    """Mock CommandOrchestrator."""
    def __init__(self, config=None):
        self.runner_config = config or self._default_config()

    def _default_config(self):
        config = Mock()
        config.commands = [CommandConfig("TestCmd", "echo test", [])]
        return config

    def has_command(self, name):
        return any(c.name == name for c in self.runner_config.commands)

    async def run_command(self, name):
        pass

    async def cancel_command(self, name):
        pass

    async def trigger(self, name):
        pass

    def get_active_handles(self, name):
        return []

    def get_history(self, name, limit=1):
        return []

    def set_lifecycle_callback(self, name, on_success=None, on_failed=None, on_cancelled=None):
        pass

    def on_event(self, event_name, callback):
        pass


class RunnerConfig:
    """Mock RunnerConfig."""
    def __init__(self, commands=None):
        self.commands = commands or [CommandConfig()]


def load_config(path):
    """Mock load_config function."""
    # Try to parse TOML to extract commands
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore

        with open(path) as f:
            raw = tomllib.loads(f.read())

        commands = []
        for cmd_data in raw.get("command", []):
            commands.append(CommandConfig(
                name=cmd_data.get("name", "test"),
                command=cmd_data.get("command", "echo test"),
                triggers=cmd_data.get("triggers", [])
            ))

        if not commands:
            commands = [CommandConfig()]

        return RunnerConfig(commands=commands)
    except Exception:
        # Fallback
        return RunnerConfig()


# Inject mocks into sys.modules before imports
cmdorc_module = MagicMock()
cmdorc_module.RunState = RunState
cmdorc_module.CommandConfig = CommandConfig
cmdorc_module.RunResult = RunResult
cmdorc_module.RunHandle = RunHandle
cmdorc_module.CommandOrchestrator = CommandOrchestrator
cmdorc_module.RunnerConfig = RunnerConfig
cmdorc_module.load_config = load_config

sys.modules['cmdorc'] = cmdorc_module
