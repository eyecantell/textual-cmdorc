"""Tests for CommandDetailsScreen."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

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
    watcher.extensions = [".py"]
    watcher.recursive = True
    watcher.trigger_emitted = "py_file_changed"
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


@pytest.fixture
async def mounted_details_screen(mock_adapter):
    """Create and mount CommandDetailsScreen for widget testing."""
    from textual.app import App

    class TestApp(App):
        def on_mount(self):
            self.push_screen(CommandDetailsScreen(cmd_name="Tests", adapter=mock_adapter))

    app = TestApp()
    async with app.run_test() as pilot:
        # Wait for screen to be pushed and mounted
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CommandDetailsScreen)
        yield screen


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
    text, path = details_screen._build_output_section_parts()

    # Verify
    assert "Output" in text
    assert "Preview" in text
    assert path == output_file


def test_build_output_section_no_output(details_screen, mock_orchestrator):
    """Output section shows 'No output available'."""
    # Setup mock status with no output
    status = Mock()
    status.last_run = None
    mock_orchestrator.get_status = Mock(return_value=status)

    # Build section
    text, path = details_screen._build_output_section_parts()

    # Verify
    assert "No output available" in text
    assert path is None


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
    result = details_screen._build_config_section_text()

    # Verify
    assert "Configuration" in result
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
    result = details_screen._build_config_section_text()

    # Verify
    assert "File watchers" in result
    assert "src" in result  # Path shown without ./ prefix
    assert ".py" in result  # extensions instead of patterns
    assert "recursive: true" in result
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
async def test_action_edit_command_now_functional(mounted_details_screen):
    """'e' key now opens config file for editing (no longer placeholder)."""
    # Mock FileLink.open_file()
    link = mounted_details_screen.query_one("#config-file-link")
    with patch.object(link, "open_file") as mock_open:
        # Call action
        await mounted_details_screen.action_edit_command()

        # Verify FileLink was activated
        mock_open.assert_called_once()


@pytest.mark.asyncio
async def test_action_open_output_no_file(mounted_details_screen, mock_orchestrator):
    """'o' key shows notification when no output file."""
    # Setup mock status with no output
    status = Mock()
    status.last_run = None
    mock_orchestrator.get_status = Mock(return_value=status)

    # Refresh to update FileLink
    mounted_details_screen._refresh_content()

    # Mock app.notify
    with patch.object(mounted_details_screen.app, "notify") as mock_notify:
        # Call action
        await mounted_details_screen.action_open_output()

        # Verify
        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        assert "No output file" in call_args[0][0]


@pytest.mark.asyncio
async def test_action_open_output_with_file(mounted_details_screen, mock_orchestrator, tmp_path):
    """'o' key opens output file via FileLink."""
    # Create temporary output file
    output_file = tmp_path / "output.txt"
    output_file.write_text("test output")

    # Setup mock status
    last_run = Mock()
    last_run.output_file = output_file

    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status = Mock(return_value=status)

    # Refresh to update FileLink
    mounted_details_screen._refresh_content()

    # Mock FileLink.open_file()
    link = mounted_details_screen.query_one("#output-file-link")
    with patch.object(link, "open_file") as mock_open:
        # Call action
        await mounted_details_screen.action_open_output()

        # Verify FileLink was activated
        mock_open.assert_called_once()


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


# ========================================================================
# FileLink Integration Tests
# ========================================================================


@pytest.mark.asyncio
async def test_output_section_contains_filelink(mounted_details_screen):
    """Output section contains FileLink widget."""
    link = mounted_details_screen.query_one("#output-file-link")
    assert link is not None


@pytest.mark.asyncio
async def test_config_section_contains_filelink(mounted_details_screen, mock_adapter):
    """Config section contains FileLink with correct path."""
    link = mounted_details_screen.query_one("#config-file-link")
    assert link is not None
    assert link.path == mock_adapter.config_path


@pytest.mark.asyncio
async def test_output_filelink_updates_on_refresh(mounted_details_screen, mock_orchestrator):
    """FileLink path updates when output file changes."""
    # Initial state: no output
    mounted_details_screen._refresh_content()
    link = mounted_details_screen.query_one("#output-file-link")
    assert link.display is False

    # Add output file
    output_file = Path("/tmp/new_output.txt")
    last_run = Mock()
    last_run.output_file = output_file
    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status.return_value = status

    # Refresh
    mounted_details_screen._refresh_content()

    # Verify update
    assert link.display is True
    assert link.path == output_file


@pytest.mark.asyncio
async def test_output_filelink_hides_when_no_output(mounted_details_screen, mock_orchestrator):
    """FileLink hides when output file becomes unavailable."""
    # Setup with output
    output_file = Path("/tmp/output.txt")
    last_run = Mock()
    last_run.output_file = output_file
    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status.return_value = status
    mounted_details_screen._refresh_content()

    link = mounted_details_screen.query_one("#output-file-link")
    assert link.display is True

    # Remove output
    last_run.output_file = None
    mounted_details_screen._refresh_content()

    # Verify hidden
    assert link.display is False


@pytest.mark.asyncio
async def test_action_open_output_activates_filelink(mounted_details_screen, mock_orchestrator):
    """'o' key programmatically opens FileLink."""
    # Setup output file
    output_file = Path("/tmp/output.txt")
    last_run = Mock()
    last_run.output_file = output_file
    status = Mock()
    status.last_run = last_run
    mock_orchestrator.get_status.return_value = status
    mounted_details_screen._refresh_content()

    # Mock FileLink.open_file()
    link = mounted_details_screen.query_one("#output-file-link")
    with patch.object(link, "open_file") as mock_open:
        await mounted_details_screen.action_open_output()
        mock_open.assert_called_once()


@pytest.mark.asyncio
async def test_action_open_output_warns_when_no_file(mounted_details_screen, mock_orchestrator):
    """'o' key shows warning when no output file available."""
    # Setup: no output file
    mounted_details_screen._refresh_content()
    link = mounted_details_screen.query_one("#output-file-link")
    assert link.display is False

    # Mock app.notify
    with patch.object(mounted_details_screen.app, "notify") as mock_notify:
        # Action should warn
        await mounted_details_screen.action_open_output()
        mock_notify.assert_called_once_with("No output file available", severity="warning")


@pytest.mark.asyncio
async def test_action_edit_command_opens_config(mounted_details_screen, mock_adapter):
    """'e' key opens config file for editing."""
    # Mock FileLink.open_file()
    link = mounted_details_screen.query_one("#config-file-link")
    with patch.object(link, "open_file") as mock_open:
        await mounted_details_screen.action_edit_command()
        mock_open.assert_called_once()
