"""Tests for CmdorcController - Phase 0 architecture."""

import pytest
import asyncio
from pathlib import Path
from textual_cmdorc.controller import CmdorcController
from cmdorc_frontend.notifier import NoOpNotifier
from cmdorc_frontend.models import ConfigValidationResult


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config file."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[keyboard]
shortcuts = { TestCmd = "1" }

[[command]]
name = "TestCmd"
command = "echo test"
triggers = []
"""
    )
    return config


def test_controller_initialization(tmp_config):
    """Test controller loads config and initializes."""
    controller = CmdorcController(tmp_config)
    assert controller is not None
    assert controller.config_path == tmp_config
    assert len(controller.hierarchy) >= 1
    assert "TestCmd" in [cmd.name for cmd in controller.hierarchy]


def test_controller_keyboard_hints(tmp_config):
    """Test FIX #1: keyboard_hints metadata exposure."""
    controller = CmdorcController(tmp_config)
    hints = controller.keyboard_hints
    assert "1" in hints
    assert hints["1"] == "TestCmd"


def test_controller_keyboard_conflicts(tmp_config):
    """Test FIX #3: keyboard_conflicts cached property."""
    # Create config with conflicting keys
    config = tmp_config.parent / "config_conflict.toml"
    config.write_text(
        """
[keyboard]
shortcuts = { Cmd1 = "1", Cmd2 = "1" }

[[command]]
name = "Cmd1"
command = "echo 1"
triggers = []

[[command]]
name = "Cmd2"
command = "echo 2"
triggers = []
"""
    )
    controller = CmdorcController(config)
    conflicts = controller.keyboard_conflicts
    assert "1" in conflicts
    assert len(conflicts["1"]) == 2
    # Verify it's cached (same object)
    assert conflicts is controller.keyboard_conflicts


@pytest.mark.asyncio
async def test_controller_attach_detach(tmp_config):
    """Test controller lifecycle - FIX #1: idempotent attach."""
    controller = CmdorcController(tmp_config, enable_watchers=False)
    loop = asyncio.get_running_loop()

    # First attach should succeed
    controller.attach(loop)
    assert controller._loop is not None

    # Second attach should be idempotent (no-op)
    controller.attach(loop)
    assert controller._loop is not None

    # Detach should work
    controller.detach()
    assert controller._loop is None


@pytest.mark.asyncio
async def test_controller_attach_with_not_running_loop(tmp_config):
    """Test RECOMMENDATION #1: attach validates loop is running."""
    controller = CmdorcController(tmp_config, enable_watchers=False)
    loop = asyncio.new_event_loop()

    with pytest.raises(RuntimeError, match="Event loop must be running"):
        controller.attach(loop)


@pytest.mark.asyncio
async def test_controller_request_run_requires_attach(tmp_config):
    """Test FIX #1: request_run requires controller to be attached."""
    controller = CmdorcController(tmp_config, enable_watchers=False)

    with pytest.raises(RuntimeError, match="Controller not attached"):
        controller.request_run("TestCmd")


@pytest.mark.asyncio
async def test_controller_request_run_async(tmp_config):
    """Test FIX #1: request_run works with attached loop."""
    controller = CmdorcController(tmp_config, enable_watchers=False)
    loop = asyncio.get_running_loop()
    controller.attach(loop)

    # request_run should not raise
    controller.request_run("TestCmd")

    # Give the scheduled task a moment to execute
    await asyncio.sleep(0.01)


def test_controller_validate_config(tmp_config):
    """Test RECOMMENDATION #3: config validation."""
    controller = CmdorcController(tmp_config)
    result = controller.validate_config()

    assert isinstance(result, ConfigValidationResult)
    assert result.commands_loaded == 1
    assert result.warnings is not None
    assert result.errors is not None


def test_controller_notifier_default_noop(tmp_config):
    """Test POLISH #3: default notifier is NoOpNotifier (silent)."""
    controller = CmdorcController(tmp_config)
    assert isinstance(controller.notifier, NoOpNotifier)


def test_controller_notifier_custom(tmp_config):
    """Test custom notifier support."""
    from cmdorc_frontend.notifier import LoggingNotifier

    notifier = LoggingNotifier()
    controller = CmdorcController(tmp_config, notifier=notifier)
    assert controller.notifier is notifier


def test_controller_enable_watchers_false(tmp_config):
    """Test enable_watchers=False prevents auto-start."""
    controller = CmdorcController(tmp_config, enable_watchers=False)
    assert controller.enable_watchers is False
