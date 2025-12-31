"""Tests for CommandDetailsScreen."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest
from conftest import CommandConfig, RunState

from textual_cmdorc.details_screen import CommandDetailsScreen


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator with configurable state."""
    orchestrator = Mock()

    # Mock _runtime for getting command config
    orchestrator._runtime = Mock()
    orchestrator._runtime.get_command = Mock(
        return_value=CommandConfig(
            name="Tests", command="pytest .", triggers=["py_file_changed", "command_success:Lint"]
        )
    )

    # Mock get_status
    status = Mock()
    status.last_run = None
    orchestrator.get_status = Mock(return_value=status)

    # Mock get_history
    orchestrator.get_history = Mock(return_value=[])

    # Mock preview_command
    preview = Mock()
    preview.command = "pytest ."
    orchestrator.preview_command = Mock(return_value=preview)

    # Mock get_trigger_graph
    orchestrator.get_trigger_graph = Mock(return_value={})

    # Mock on_event and lifecycle callbacks
    orchestrator.on_event = Mock()

    return orchestrator


@pytest.fixture
def mock_adapter(mock_orchestrator, tmp_path):
    """Create mock OrchestratorAdapter."""
    adapter = Mock()
    adapter.orchestrator = mock_orchestrator
    adapter.config_path = tmp_path / "config.toml"

    # Mock keyboard config
    keyboard_config = Mock()
    keyboard_config.shortcuts = {"Tests": "1", "Lint": "2"}
    keyboard_config.enabled = True
    adapter.keyboard_config = keyboard_config

    # Mock watchers
    watcher = Mock()
    watcher.dir = Path("./src")
    watcher.patterns = ["**/*.py"]
    watcher.trigger = "py_file_changed"
    watcher.debounce_ms = 300
    adapter._watchers = [watcher]

    # Mock on_command callbacks
    adapter.on_command_success = Mock()
    adapter.on_command_failed = Mock()
    adapter.on_command_cancelled = Mock()

    # Mock request_run
    adapter.request_run = Mock()

    return adapter


@pytest.fixture
def details_screen(mock_adapter):
    """Create CommandDetailsScreen instance for testing."""
    return CommandDetailsScreen(cmd_name="Tests", adapter=mock_adapter)


# ========================================================================
# Content Builder Tests
# ========================================================================


def test_build_status_section_success(details_screen, mock_orchestrator):
    """Status section shows success state correctly."""
    # Setup mock status
    last_run = Mock()
    last_run.state = RunState.SUCCESS
    last_run.time_ago_str = "5s ago"
    last_run.duration_str = "1.2s"
    last_run.return_code = 0

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_status_section()

    # Verify
    assert "Status" in result
    assert "✅" in result
    assert "Success" in result
    assert "5s ago" in result
    assert "1.2s" in result
    assert "Exit code: 0" in result


def test_build_status_section_failed(details_screen, mock_orchestrator):
    """Status section shows failed state with exit code."""
    # Setup mock status
    last_run = Mock()
    last_run.state = RunState.FAILED
    last_run.time_ago_str = "2m ago"
    last_run.duration_str = "0.5s"
    last_run.return_code = 1

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_status_section()

    # Verify
    assert "❌" in result
    assert "Failed" in result
    assert "Exit code: 1" in result


def test_build_status_section_no_runs(details_screen, mock_orchestrator):
    """Status section shows 'Not yet run' when no history."""
    # Setup mock status
    status = Mock()
    status.last_run = None
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_status_section()

    # Verify
    assert "Not yet run" in result


def test_build_current_run_section_running(details_screen, mock_orchestrator):
    """Current run section shows elapsed time and trigger chain."""
    # Setup mock running status
    last_run = Mock()
    last_run.state = RunState.RUNNING
    last_run.start_time = datetime.now()
    last_run.trigger_chain = ["py_file_changed"]
    last_run.resolved_command = Mock(command="pytest .")

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_current_run_section()

    # Verify
    assert result is not None
    assert "Current Run" in result
    assert "⏳" in result
    assert "Running for" in result


def test_build_current_run_section_not_running(details_screen, mock_orchestrator):
    """Current run section returns None when not running."""
    # Setup mock idle status
    last_run = Mock()
    last_run.state = RunState.SUCCESS

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_current_run_section()

    # Verify
    assert result is None


def test_build_triggers_section_with_downstream(details_screen, mock_orchestrator):
    """Triggers section shows triggers and downstream commands."""
    # Setup mock trigger graph
    mock_orchestrator.get_trigger_graph = Mock(
        return_value={"command_success:Tests": ["Deploy", "Notify"], "command_failed:Tests": ["NotifySlack"]}
    )

    # Build section
    result = details_screen._build_triggers_section()

    # Verify
    assert "Triggers" in result
    assert "py_file_changed" in result
    assert "After Lint succeeds" in result
    assert "manual" in result
    assert "On success" in result
    assert "Deploy" in result
    assert "On failure" in result
    assert "NotifySlack" in result


def test_build_history_section_with_runs(details_screen, mock_orchestrator):
    """History section shows formatted run history."""
    # Setup mock history
    run1 = Mock()
    run1.state = RunState.SUCCESS
    run1.time_ago_str = "5s ago"
    run1.duration_str = "1.2s"
    run1.return_code = 0

    run2 = Mock()
    run2.state = RunState.FAILED
    run2.time_ago_str = "2m ago"
    run2.duration_str = "0.9s"
    run2.return_code = 1

    mock_orchestrator.get_history = Mock(return_value=[run1, run2])

    # Build section
    result = details_screen._build_history_section()

    # Verify
    assert "Run History" in result
    assert "✅" in result
    assert "❌" in result
    assert "1.2s" in result
    assert "exit 1" in result


def test_build_history_section_empty(details_screen, mock_orchestrator):
    """History section shows 'No runs recorded' when empty."""
    # Setup empty history
    mock_orchestrator.get_history = Mock(return_value=[])

    # Build section
    result = details_screen._build_history_section()

    # Verify
    assert "No runs recorded" in result


def test_build_output_section_with_preview(details_screen, mock_orchestrator, tmp_path):
    """Output section shows file path and preview."""
    # Create temporary output file
    output_file = tmp_path / "output.txt"
    output_file.write_text("test output line 1\ntest output line 2\ntest output line 3\n")

    # Setup mock status
    last_run = Mock()
    last_run.output_file = output_file

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_output_section()

    # Verify
    assert "Output" in result
    assert str(output_file) in result
    assert "Preview" in result


def test_build_output_section_no_output(details_screen, mock_orchestrator):
    """Output section shows 'No output available'."""
    # Setup mock status with no output
    status = Mock()
    status.last_run = None
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    result = details_screen._build_output_section()

    # Verify
    assert "No output available" in result


def test_build_config_section_non_defaults(details_screen, mock_orchestrator, mock_adapter):
    """Config section only shows non-default values."""
    # Setup mock config with non-default values
    config = CommandConfig(name="Tests", command="pytest .", triggers=[])
    config.timeout_secs = 300
    config.max_concurrent = 2
    config.debounce_in_ms = 500
    config.on_retrigger = "ignore"
    config.keep_in_memory = 10
    config.cwd = "/app"
    config.debounce_mode = "completion"

    mock_orchestrator._runtime.get_command = Mock(return_value=config)

    # Build section
    result = details_screen._build_config_section()

    # Verify
    assert "Configuration" in result
    assert str(mock_adapter.config_path) in result
    assert "Timeout: 300s" in result
    assert "Max concurrent: 2" in result
    assert "Debounce: 500ms" in result
    assert "On retrigger: ignore" in result
    assert "Keep in memory: 10 runs" in result
    assert "Working directory: /app" in result


def test_build_config_section_with_watchers(details_screen, mock_orchestrator, mock_adapter):
    """Config section shows relevant file watchers."""
    # Setup config with matching trigger
    config = CommandConfig(name="Tests", command="pytest .", triggers=["py_file_changed"])
    config.timeout_secs = None
    config.max_concurrent = 1
    config.debounce_in_ms = 0
    config.on_retrigger = "cancel_and_restart"
    config.keep_in_memory = 3
    config.cwd = None

    mock_orchestrator._runtime.get_command = Mock(return_value=config)

    # Build section
    result = details_screen._build_config_section()

    # Verify
    assert "File watchers" in result
    assert "src" in result  # Path shown without ./ prefix
    assert "**/*.py" in result
    assert "py_file_changed" in result
    assert "300ms" in result


# ========================================================================
# Keyboard Action Tests
# ========================================================================


@pytest.mark.asyncio
async def test_action_run_command(details_screen, mock_adapter):
    """'r' key triggers command execution."""
    # Mock app using patch.object
    mock_app = Mock()
    with patch.object(type(details_screen), "app", new_callable=lambda: mock_app):
        # Call action
        await details_screen.action_run_command()

        # Verify
        mock_adapter.request_run.assert_called_once_with("Tests")
        mock_app.notify.assert_called()


@pytest.mark.asyncio
async def test_action_copy_command(details_screen, mock_orchestrator):
    """'c' key copies resolved command to clipboard."""
    # Mock app using patch.object
    mock_app = Mock()
    with patch.object(type(details_screen), "app", new_callable=lambda: mock_app):
        # Call action
        await details_screen.action_copy_command()

        # Verify
        mock_app.copy_to_clipboard.assert_called_once_with("pytest .")
        mock_app.notify.assert_called()


@pytest.mark.asyncio
async def test_action_edit_command_placeholder(details_screen):
    """'e' key shows placeholder notification."""
    # Mock app using patch.object
    mock_app = Mock()
    with patch.object(type(details_screen), "app", new_callable=lambda: mock_app):
        # Call action
        await details_screen.action_edit_command()

        # Verify
        mock_app.notify.assert_called_once()
        call_args = mock_app.notify.call_args
        assert "coming soon" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_action_open_output_no_file(details_screen, mock_orchestrator):
    """'o' key shows notification when no output file."""
    # Setup mock status with no output
    status = Mock()
    status.last_run = None
    mock_orchestrator.get_status = Mock(return_value=status)

    # Mock app using patch.object
    mock_app = Mock()
    with patch.object(type(details_screen), "app", new_callable=lambda: mock_app):
        # Call action
        await details_screen.action_open_output()

        # Verify
        mock_app.notify.assert_called_once()
        call_args = mock_app.notify.call_args
        assert "No output file" in call_args[0][0]


@pytest.mark.asyncio
async def test_action_open_output_with_file(details_screen, mock_orchestrator, tmp_path):
    """'o' key opens output file in editor."""
    # Create temporary output file
    output_file = tmp_path / "output.txt"
    output_file.write_text("test output")

    # Setup mock status
    last_run = Mock()
    last_run.output_file = output_file

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Mock app using patch.object
    mock_app = Mock()
    mock_app.suspend = MagicMock()

    with (
        patch.object(type(details_screen), "app", new_callable=lambda: mock_app),
        patch("textual_cmdorc.details_screen.subprocess.run") as mock_run,
    ):
        # Call action
        await details_screen.action_open_output()

        # Verify subprocess was called (would open editor)
        mock_run.assert_called_once()


# ========================================================================
# Edge Case Tests
# ========================================================================


def test_refresh_content_command_deleted(details_screen, mock_orchestrator):
    """Handles gracefully when command is deleted while modal open."""
    # Mock orchestrator to raise exception
    mock_orchestrator.get_status = Mock(side_effect=Exception("Command not found"))

    # Patch is_mounted property to return True
    with patch.object(type(details_screen), "is_mounted", new_callable=PropertyMock, return_value=True):
        # Should not raise exception - just log error
        details_screen._refresh_content()

        # If we get here, the test passed (no exception raised)


def test_get_downstream_commands(details_screen, mock_orchestrator):
    """Helper method correctly retrieves downstream commands."""
    # Setup mock trigger graph
    mock_orchestrator.get_trigger_graph = Mock(
        return_value={"command_success:Tests": ["Deploy", "Notify"], "command_failed:Tests": ["NotifySlack"]}
    )

    # Get success downstream
    success_downstream = details_screen._get_downstream_commands("Tests", "success")
    assert success_downstream == ["Deploy", "Notify"]

    # Get failure downstream
    failure_downstream = details_screen._get_downstream_commands("Tests", "failed")
    assert failure_downstream == ["NotifySlack"]


def test_build_status_section_error_handling(details_screen, mock_orchestrator):
    """Status section handles errors gracefully."""
    # Mock orchestrator to raise exception
    mock_orchestrator.get_status = Mock(side_effect=Exception("Test error"))

    # Build section
    result = details_screen._build_status_section()

    # Should return error message
    assert "Error loading status" in result
