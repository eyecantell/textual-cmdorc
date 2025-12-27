"""Tests for CmdorcApp TUI application."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from cmdorc import RunHandle

from textual_cmdorc.cmdorc_app import CmdorcApp

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


class TestCmdorcAppLifecycleCallbacks:
    """Test lifecycle callback methods."""

    @pytest.mark.asyncio
    async def test_on_command_success_with_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_success sets output_path when output_file exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()
            mock_link.output_path = None

            # Mock _get_link to return our mock link
            app._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            app.tooltip_builder = Mock()
            app.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test result")
            app.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            app.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle with output_file
            output_file = Path("/tmp/test_output.txt")
            handle = RunHandle(name="Test", output_file=output_file)

            # Call the callback
            app._on_command_success("Test", handle)

            # Verify set_output_path was called
            mock_link.set_output_path.assert_called_once_with(output_file)
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_success_without_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_success when output_file is None."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()

            # Mock _get_link to return our mock link
            app._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            app.tooltip_builder = Mock()
            app.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test result")
            app.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            app.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle without output_file
            handle = RunHandle(name="Test", output_file=None)

            # Call the callback
            app._on_command_success("Test", handle)

            # Verify set_output_path was NOT called
            mock_link.set_output_path.assert_not_called()
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_failed_with_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_failed sets output_path when output_file exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()

            app._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            app.tooltip_builder = Mock()
            app.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test failed")
            app.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            app.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle with output_file
            output_file = Path("/tmp/test_output.txt")
            handle = RunHandle(name="Test", output_file=output_file)

            # Call the callback
            app._on_command_failed("Test", handle)

            # Verify set_output_path was called
            mock_link.set_output_path.assert_called_once_with(output_file)
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_cancelled_with_output_file(self, mock_adapter, mock_config_path):
        """Test _on_command_cancelled sets output_path when output_file exists."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock link
            mock_link = Mock()
            mock_link.set_output_path = Mock()
            mock_link.set_status = Mock()

            app._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            app.tooltip_builder = Mock()
            app.tooltip_builder.build_status_tooltip_completed = Mock(return_value="Test cancelled")
            app.tooltip_builder.build_play_tooltip = Mock(return_value="Play test")
            app.tooltip_builder.build_output_tooltip = Mock(return_value="Output test")

            # Create a handle with output_file
            output_file = Path("/tmp/test_output.txt")
            handle = RunHandle(name="Test", output_file=output_file)

            # Call the callback
            app._on_command_cancelled("Test", handle)

            # Verify set_output_path was called
            mock_link.set_output_path.assert_called_once_with(output_file)
            mock_link.set_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_command_started(self, mock_adapter, mock_config_path):
        """Test _on_command_started updates link status."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock link
            mock_link = Mock()
            mock_link.set_status = Mock()

            app._get_link = Mock(return_value=mock_link)

            # Mock tooltip_builder
            app.tooltip_builder = Mock()
            app.tooltip_builder.build_status_tooltip_running = Mock(return_value="Test running")
            app.tooltip_builder.build_stop_tooltip = Mock(return_value="Stop test")

            # Create a handle
            handle = RunHandle(name="Test")

            # Call the callback
            app._on_command_started("Test", handle)

            # Verify running_commands was updated
            assert "Test" in app.running_commands

            # Verify set_status was called with running=True
            mock_link.set_status.assert_called_once()
            call_kwargs = mock_link.set_status.call_args[1]
            assert call_kwargs["running"] is True
            assert call_kwargs["icon"] == "⏳"


class TestCmdorcAppReload:
    """Test configuration reload functionality."""

    @pytest.mark.asyncio
    async def test_reload_config_awaits_removal(self, mock_adapter, mock_config_path):
        """Test that reload awaits file_list.remove()."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock file_list with async remove
            mock_file_list = Mock()
            mock_file_list.remove = AsyncMock()
            app.file_list = mock_file_list

            # Mock other dependencies
            app.adapter = mock_adapter
            app.query_one = Mock(return_value=Mock())  # Footer mock
            app.mount = AsyncMock()
            app._bind_keyboard_shortcuts = Mock()
            app._build_idle_tooltip = Mock(return_value="Idle")
            app._get_command_string = Mock(return_value="echo test")
            app.notify = Mock()

            # Call reload
            await app.action_reload_config()

            # Verify remove was awaited
            mock_file_list.remove.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reload_config_detaches_old_adapter(self, mock_adapter, mock_config_path):
        """Test that reload detaches the old adapter."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Set up mocks
            app.file_list = Mock()
            app.file_list.remove = AsyncMock()
            app.adapter = mock_adapter
            app.query_one = Mock(return_value=Mock())
            app.mount = AsyncMock()
            app._bind_keyboard_shortcuts = Mock()
            app._build_idle_tooltip = Mock(return_value="Idle")
            app._get_command_string = Mock(return_value="echo test")
            app.notify = Mock()

            # Call reload
            await app.action_reload_config()

            # Verify detach was called
            mock_adapter.detach.assert_called_once()


class TestCmdorcAppGetLink:
    """Test _get_link helper method."""

    def test_get_link_returns_link(self, mock_adapter, mock_config_path):
        """Test _get_link returns CommandLink using query_one."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Create a mock link
            mock_link = Mock()

            # Mock query_one to return the mock link
            app.query_one = Mock(return_value=mock_link)

            result = app._get_link("Test")

            # Should call query_one with sanitized ID
            app.query_one.assert_called_once()
            assert result == mock_link

    def test_get_link_returns_none_for_unknown_command(self, mock_adapter, mock_config_path):
        """Test _get_link returns None when query_one raises exception."""
        with patch("textual_cmdorc.cmdorc_app.OrchestratorAdapter", return_value=mock_adapter):
            app = CmdorcApp(config_path=mock_config_path)

            # Mock query_one to raise exception (command not found)
            app.query_one = Mock(side_effect=Exception("No screens on stack"))

            result = app._get_link("Test")

            assert result is None
