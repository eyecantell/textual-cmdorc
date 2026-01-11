"""Tests for CmdorcApp TUI application and CmdorcWidget."""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from cmdorc import RunHandle

from textual_cmdorc.cmdorc_app import CmdorcWidget

# Mock textual_filelink before imports
mock_filelink = MagicMock()


# Create CommandLink mock with message classes
class MockCommandLink:
    class PlayClicked:
        pass

    class StopClicked:
        pass

    class SettingsClicked:
        pass

    class OutputClicked:
        pass


mock_filelink.CommandLink = MockCommandLink
mock_filelink.FileLinkList = MagicMock
mock_filelink.sanitize_id = lambda x: x.lower().replace(" ", "-")

sys.modules["textual_filelink"] = mock_filelink


@pytest.fixture
def mock_adapter():
    """Create a mock OrchestratorAdapter."""
    adapter = Mock()
    adapter.config_path = Path("test_config.toml")
    adapter.get_command_names = Mock(return_value=["Test", "Build", "Lint"])
    adapter.attach = Mock()
    adapter.detach = Mock()
    adapter.request_run = Mock()
    adapter.request_cancel = Mock()
    adapter.preview_command = Mock(return_value="echo test")

    # Mock orchestrator
    adapter.orchestrator = Mock()
    adapter.orchestrator.on_event = Mock()
    adapter.orchestrator.get_active_handles = Mock(return_value=[])
    adapter.orchestrator.get_history = Mock(return_value=[])

    # Mock runtime with get_command
    mock_runtime = Mock()
    mock_cmd_config = Mock()
    mock_cmd_config.triggers = ["manual", "file_changed"]
    mock_runtime.get_command = Mock(return_value=mock_cmd_config)
    adapter.orchestrator._runtime = mock_runtime

    # Mock keyboard config
    adapter.keyboard_config = Mock()
    adapter.keyboard_config.enabled = True
    adapter.keyboard_config.show_in_tooltips = True
    adapter.keyboard_config.shortcuts = {"Test": "1", "Build": "2"}

    return adapter


@pytest.fixture
def mock_config_path(tmp_path):
    """Create a temporary config file."""
    config_path = tmp_path / "test_config.toml"
    config_path.write_text("""
[[command]]
name = "Test"
command = "echo test"
triggers = []

[[command]]
name = "Build"
command = "echo build"
triggers = []
""")
    return config_path


class TestCmdorcWidgetLifecycleCallbacks:
    """Test CmdorcWidget lifecycle callback methods."""

    @pytest.mark.asyncio
    async def test_on_command_success_with_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_success sets output_path when output_file exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()
            mock_link.output_path = None

            # Mock _get_link to return our mock link
            widget._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test result")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle with output_file
            output_file = Path("/tmp/test_output.txt")
            handle = RunHandle(name="Test", output_file=output_file)
            handle.end_time = datetime.now()  # Add end_time for timer tests
            handle.time_ago_str = "1m ago"  # Add time_ago_str for tooltips

            # Call the callback
            widget._on_command_success("Test", handle)

            # Verify set_output_path was called
            mock_link.set_output_path.assert_called_once_with(output_file)
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_success_without_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_success when output_file is None."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()

            # Mock _get_link to return our mock link
            widget._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test result")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle without output_file
            handle = RunHandle(name="Test", output_file=None)
            handle.end_time = datetime.now()  # Add end_time for timer tests
            handle.time_ago_str = "1m ago"  # Add time_ago_str for tooltips

            # Call the callback
            widget._on_command_success("Test", handle)

            # Verify set_output_path was NOT called
            mock_link.set_output_path.assert_not_called()
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_failed_with_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_failed sets output_path when output_file exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()

            widget._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test failed")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle with output_file
            output_file = Path("/tmp/test_output.txt")
            handle = RunHandle(name="Test", output_file=output_file)
            handle.end_time = datetime.now()  # Add end_time for timer tests
            handle.time_ago_str = "1m ago"  # Add time_ago_str for tooltips

            # Call the callback
            widget._on_command_failed("Test", handle)

            # Verify set_output_path was called
            mock_link.set_output_path.assert_called_once_with(output_file)
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_cancelled_with_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_cancelled sets output_path when output_file exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()

            widget._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test cancelled")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle with output_file
            output_file = Path("/tmp/test_output.txt")
            handle = RunHandle(name="Test", output_file=output_file)
            handle.end_time = datetime.now()  # Add end_time for timer tests
            handle.time_ago_str = "1m ago"  # Add time_ago_str for tooltips

            # Call the callback
            widget._on_command_cancelled("Test", handle)

            # Verify set_output_path was called
            mock_link.set_output_path.assert_called_once_with(output_file)
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_started(self, mock_adapter, mock_config_path):
        """Test _on_command_started updates link status."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link
            mock_link = Mock()
            mock_link.set_status = Mock()

            widget._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_running = Mock(return_value="Test running")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop test")

            # Create a handle
            handle = RunHandle(name="Test")
            handle.start_time = datetime.now()  # Add start_time for timer tests

            # Call the callback
            widget._on_command_started("Test", handle)

            # Verify running_commands was updated
            assert "Test" in widget.running_commands

            # Verify set_status was called with running=True (no icon, uses default spinner)
            mock_link.set_status.assert_called_once()
            call_kwargs = mock_link.set_status.call_args[1]
            assert call_kwargs["running"] is True
            assert "icon" not in call_kwargs  # Uses textual-filelink default spinner

    @pytest.mark.asyncio
    async def test_on_command_started_clears_output_path(self, mock_adapter, mock_config_path):
        """Test that starting a command clears the output path and updates tooltip."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link with output path clearing capability
            mock_link = Mock()
            mock_link.set_status = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_name_tooltip = Mock()

            widget._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_running = Mock(return_value="Test running")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop test")
            widget.tooltip_builder.build_output_tooltip = Mock(
                return_value="Test\n\nCommand running - output will be available after completion"
            )

            # Create a handle
            handle = RunHandle(name="Test")
            handle.start_time = datetime.now()

            # Call the callback
            widget._on_command_started("Test", handle)

            # Verify output path was cleared
            mock_link.set_output_path.assert_called_once_with(None)

            # Verify output tooltip was updated with is_running=True via set_name_tooltip
            widget.tooltip_builder.build_output_tooltip.assert_called_once_with("Test", is_running=True)
            mock_link.set_name_tooltip.assert_called_once_with(
                "Test\n\nCommand running - output will be available after completion",
                append_shortcuts=False,
            )

            # Verify set_status was also called (normal behavior)
            mock_link.set_status.assert_called_once()


class TestCmdorcWidgetReload:
    """Test CmdorcWidget configuration reload functionality."""

    @pytest.mark.asyncio
    async def test_reload_config_awaits_removal(self, mock_adapter, mock_config_path):
        """Test that reload awaits file_list.remove()."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock file_list with async remove
            mock_file_list = Mock()
            mock_file_list.remove = AsyncMock()
            widget.file_list = mock_file_list

            # Mock other dependencies
            widget.adapter = mock_adapter
            widget.mount = AsyncMock()
            widget._bind_keyboard_shortcuts = Mock()
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_idle = Mock(return_value="Idle")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output")

            # Call reload
            await widget.reload_config()

            # Verify remove was awaited
            mock_file_list.remove.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reload_config_detaches_old_adapter(self, mock_adapter, mock_config_path):
        """Test that reload detaches the old adapter."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Set up mocks
            widget.file_list = Mock()
            widget.file_list.remove = AsyncMock()
            widget.adapter = mock_adapter
            widget.mount = AsyncMock()
            widget._bind_keyboard_shortcuts = Mock()
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_idle = Mock(return_value="Idle")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output")

            # Call reload
            await widget.reload_config()

            # Verify detach was called
            mock_adapter.detach.assert_called_once()


class TestCmdorcWidgetGetLink:
    """Test CmdorcWidget _get_link helper method."""

    def test_get_link_returns_link(self, mock_adapter, mock_config_path):
        """Test _get_link returns CommandLink using query_one."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Create a mock link
            mock_link = Mock()

            # Mock query_one to return the mock link
            widget.query_one = Mock(return_value=mock_link)

            result = widget._get_link("Test")

            # Should call query_one with sanitized ID
            widget.query_one.assert_called_once()
            assert result == mock_link

    def test_get_link_returns_none_for_unknown_command(self, mock_adapter, mock_config_path):
        """Test _get_link returns None when query_one raises exception."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Mock query_one to raise exception (command not found)
            widget.query_one = Mock(side_effect=Exception("No screens on stack"))

            result = widget._get_link("Test")

            assert result is None


class TestCmdorcWidgetInitialStatus:
    """Test CmdorcWidget initial status icon reflects historical run state."""

    @pytest.mark.asyncio
    async def test_on_mount_sets_success_icon_from_history(self, mock_adapter, mock_config_path):
        """Test that on_mount sets success icon when last run succeeded."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            # Mock status with successful last run
            mock_status = Mock()
            mock_last_run = Mock()
            mock_last_run.state.name = "SUCCESS"
            mock_last_run.output_file = None
            mock_last_run.end_time = datetime.now()  # Add end_time for timer tests
            mock_last_run.time_ago_str = "1m ago"  # Add time_ago_str for tooltips
            mock_status.last_run = mock_last_run
            mock_adapter.orchestrator.get_status.return_value = mock_status

            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Ensure adapter is set
            widget.adapter = mock_adapter

            # Mock file_list
            widget.file_list = Mock()
            widget.file_list.add_item = Mock()

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_idle = Mock(return_value="Idle")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output")

            # Call on_mount
            await widget.on_mount()

            # Verify CommandLink was created with success icon
            widget.file_list.add_item.assert_called()
            link_arg = widget.file_list.add_item.call_args[0][0]
            assert link_arg._status_icon == "✅"

    @pytest.mark.asyncio
    async def test_on_mount_sets_failed_icon_from_history(self, mock_adapter, mock_config_path):
        """Test that on_mount sets failed icon when last run failed."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            # Mock status with failed last run
            mock_status = Mock()
            mock_last_run = Mock()
            mock_last_run.state.name = "FAILED"
            mock_last_run.output_file = None
            mock_last_run.end_time = datetime.now()  # Add end_time for timer tests
            mock_last_run.time_ago_str = "1m ago"  # Add time_ago_str for tooltips
            mock_status.last_run = mock_last_run
            mock_adapter.orchestrator.get_status.return_value = mock_status

            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Ensure adapter is set
            widget.adapter = mock_adapter

            # Mock file_list
            widget.file_list = Mock()
            widget.file_list.add_item = Mock()

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_idle = Mock(return_value="Idle")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output")

            # Call on_mount
            await widget.on_mount()

            # Verify CommandLink was created with failed icon
            widget.file_list.add_item.assert_called()
            link_arg = widget.file_list.add_item.call_args[0][0]
            assert link_arg._status_icon == "❌"

    @pytest.mark.asyncio
    async def test_on_mount_sets_cancelled_icon_from_history(self, mock_adapter, mock_config_path):
        """Test that on_mount sets cancelled icon when last run was cancelled."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            # Mock status with cancelled last run
            mock_status = Mock()
            mock_last_run = Mock()
            mock_last_run.state.name = "CANCELLED"
            mock_last_run.output_file = None
            mock_last_run.end_time = datetime.now()  # Add end_time for timer tests
            mock_last_run.time_ago_str = "1m ago"  # Add time_ago_str for tooltips
            mock_status.last_run = mock_last_run
            mock_adapter.orchestrator.get_status.return_value = mock_status

            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Ensure adapter is set
            widget.adapter = mock_adapter

            # Mock file_list
            widget.file_list = Mock()
            widget.file_list.add_item = Mock()

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_idle = Mock(return_value="Idle")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output")

            # Call on_mount
            await widget.on_mount()

            # Verify CommandLink was created with cancelled icon
            widget.file_list.add_item.assert_called()
            link_arg = widget.file_list.add_item.call_args[0][0]
            assert link_arg._status_icon == "⚠️"

    @pytest.mark.asyncio
    async def test_on_mount_sets_idle_icon_when_no_history(self, mock_adapter, mock_config_path):
        """Test that on_mount sets idle icon when no history exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            # Mock status with no last run
            mock_status = Mock()
            mock_status.last_run = None
            mock_adapter.orchestrator.get_status.return_value = mock_status

            widget = CmdorcWidget(config_path=str(mock_config_path))

            # Ensure adapter is set
            widget.adapter = mock_adapter

            # Mock file_list
            widget.file_list = Mock()
            widget.file_list.add_item = Mock()

            # Mock tooltip_builder
            widget.tooltip_builder = Mock()
            widget.tooltip_builder.build_status_tooltip_idle = Mock(return_value="Idle")
            widget.tooltip_builder.build_play_tooltip = Mock(return_value="Play")
            widget.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop")
            widget.tooltip_builder.build_output_tooltip = Mock(return_value="Output")

            # Call on_mount
            await widget.on_mount()

            # Verify CommandLink was created with idle icon
            widget.file_list.add_item.assert_called()
            link_arg = widget.file_list.add_item.call_args[0][0]
            assert link_arg._status_icon == "◯"
