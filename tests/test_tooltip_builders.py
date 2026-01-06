"""Tests for TooltipBuilder class."""

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import Mock

import pytest

from textual_cmdorc.tooltip_builders import TooltipBuilder


@pytest.fixture
def mock_adapter():
    """Create a mock OrchestratorAdapter."""
    adapter = Mock()
    adapter.orchestrator = Mock()
    adapter.keyboard_config = Mock()
    adapter.keyboard_config.shortcuts = {}
    return adapter


class TestTooltipBuilderStatusTooltips:
    """Tests for status tooltip builders."""

    def test_build_status_tooltip_idle_no_history(self, mock_adapter):
        """Test idle tooltip when no history exists."""
        mock_adapter.orchestrator.get_history.return_value = []
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="echo test")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_idle("Test")

        assert "Not yet run" in tooltip
        assert "Test" in tooltip

    def test_build_status_tooltip_idle_with_single_history(self, mock_adapter):
        """Test idle tooltip with single historical run."""
        mock_result = Mock()
        mock_result.state.name = "SUCCESS"
        mock_result.end_time = datetime.now().timestamp()
        mock_result.duration_str = "1.5s"
        mock_result.time_ago_str = "1m ago"

        mock_adapter.orchestrator.get_history.return_value = [mock_result]
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="echo test")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_idle("Test")

        assert "Last run:" in tooltip
        assert "✅" in tooltip
        assert "echo test" in tooltip

    def test_build_status_tooltip_idle_with_multiple_history(self, mock_adapter):
        """Test idle tooltip with multiple historical runs."""
        mock_results = []
        for i in range(3):
            result = Mock()
            result.state.name = "SUCCESS"
            result.end_time = datetime.now().timestamp()
            result.duration_str = f"{i}.5s"
            result.time_ago_str = f"{i}m ago"
            mock_results.append(result)

        mock_adapter.orchestrator.get_history.return_value = mock_results
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="echo test")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_idle("Test")

        assert "Last 3 runs:" in tooltip
        assert tooltip.count("✅") == 3

    def test_build_status_tooltip_idle_with_failed_history(self, mock_adapter):
        """Test idle tooltip with failed run in history."""
        mock_result = Mock()
        mock_result.state.name = "FAILED"
        mock_result.end_time = datetime.now().timestamp()
        mock_result.duration_str = "1.5s"
        mock_result.time_ago_str = "1m ago"

        mock_adapter.orchestrator.get_history.return_value = [mock_result]
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="echo test")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_idle("Test")

        assert "❌" in tooltip

    def test_build_status_tooltip_running(self, mock_adapter):
        """Test running tooltip."""
        mock_handle = Mock()
        mock_handle.start_time = datetime.now().timestamp()

        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_running("Test", mock_handle)

        assert "Running" in tooltip or "⏳" in tooltip
        assert "pytest tests/" in tooltip

    def test_build_status_tooltip_running_no_handle(self, mock_adapter):
        """Test running tooltip without handle."""
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_running("Test", None)

        assert "Running" in tooltip

    def test_build_status_tooltip_completed_single_run(self, mock_adapter):
        """Test completed tooltip with single run."""
        mock_handle = Mock()
        mock_handle.state.name = "SUCCESS"
        mock_handle.end_time = datetime.now().timestamp()
        mock_handle.duration_str = "1.5s"
        mock_handle.time_ago_str = "1m ago"

        mock_adapter.orchestrator.get_history.return_value = [mock_handle]
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="echo test")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_completed("Test", mock_handle)

        assert "Last run:" in tooltip
        assert "✅" in tooltip

    def test_build_status_tooltip_completed_multiple_runs(self, mock_adapter):
        """Test completed tooltip with multiple runs."""
        mock_results = []
        for i in range(3):
            result = Mock()
            result.state.name = "SUCCESS"
            result.end_time = datetime.now().timestamp()
            result.duration_str = f"{i}.5s"
            result.time_ago_str = f"{i}m ago"
            mock_results.append(result)

        mock_adapter.orchestrator.get_history.return_value = mock_results
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="echo test")

        mock_handle = Mock()
        mock_handle.state.name = "SUCCESS"

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_status_tooltip_completed("Test", mock_handle)

        assert "Last 3 runs:" in tooltip


class TestTooltipBuilderPlayStopTooltips:
    """Tests for play/stop tooltip builders."""

    def test_build_play_tooltip_basic(self, mock_adapter):
        """Test basic play tooltip."""
        mock_config = Mock()
        mock_config.triggers = ["manual"]
        mock_config.cancel_on_triggers = []

        mock_adapter.orchestrator._runtime.get_command.return_value = mock_config
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")
        mock_adapter.orchestrator.get_trigger_graph.return_value = {}

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_play_tooltip("Test")

        assert "▶️ Run Test" in tooltip
        assert "pytest tests/" in tooltip
        assert "manual" in tooltip

    def test_build_play_tooltip_with_keyboard_shortcut(self, mock_adapter):
        """Test play tooltip with keyboard shortcut."""
        mock_config = Mock()
        mock_config.triggers = []
        mock_config.cancel_on_triggers = []

        mock_adapter.orchestrator._runtime.get_command.return_value = mock_config
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")
        mock_adapter.orchestrator.get_trigger_graph.return_value = {}
        mock_adapter.keyboard_config.shortcuts = {"Test": "1"}

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_play_tooltip("Test")

        assert "[1] manual" in tooltip

    def test_build_play_tooltip_with_triggers(self, mock_adapter):
        """Test play tooltip with trigger sources."""
        mock_config = Mock()
        mock_config.triggers = ["command_success:Lint", "file_changed"]
        mock_config.cancel_on_triggers = []

        mock_adapter.orchestrator._runtime.get_command.return_value = mock_config
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")
        mock_adapter.orchestrator.get_trigger_graph.return_value = {}

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_play_tooltip("Test")

        assert "After Lint succeeds" in tooltip
        assert "file_changed" in tooltip

    def test_build_play_tooltip_with_downstream_success(self, mock_adapter):
        """Test play tooltip with downstream commands on success."""
        mock_config = Mock()
        mock_config.triggers = []
        mock_config.cancel_on_triggers = []

        mock_adapter.orchestrator._runtime.get_command.return_value = mock_config
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")
        mock_adapter.orchestrator.get_trigger_graph.return_value = {"command_success:Test": ["Deploy", "Notify"]}

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_play_tooltip("Test")

        assert "On success →" in tooltip
        assert "Deploy" in tooltip
        assert "Notify" in tooltip

    def test_build_play_tooltip_with_cancel_triggers(self, mock_adapter):
        """Test play tooltip with cancel triggers."""
        mock_config = Mock()
        mock_config.triggers = []
        mock_config.cancel_on_triggers = ["file_changed", "manual_stop"]

        mock_adapter.orchestrator._runtime.get_command.return_value = mock_config
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")
        mock_adapter.orchestrator.get_trigger_graph.return_value = {}

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_play_tooltip("Test")

        assert "Cancel on:" in tooltip
        assert "file_changed" in tooltip

    def test_build_stop_tooltip_basic(self, mock_adapter):
        """Test basic stop tooltip."""
        mock_adapter.orchestrator.preview_command.return_value = Mock(command="pytest tests/")

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_stop_tooltip("Test", None)

        assert "⏹️ Stop Test" in tooltip
        assert "pytest tests/" in tooltip

    def test_build_stop_tooltip_with_handle(self, mock_adapter):
        """Test stop tooltip with running handle."""
        mock_handle = Mock()
        mock_handle.start_time = datetime.now().timestamp()
        mock_handle.resolved_command = Mock(command="pytest tests/ -v")
        mock_handle.trigger_chain = []

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_stop_tooltip("Test", mock_handle)

        assert "Running for" in tooltip
        assert "pytest tests/ -v" in tooltip

    def test_build_stop_tooltip_with_trigger_chain(self, mock_adapter):
        """Test stop tooltip with trigger chain."""
        mock_handle = Mock()
        mock_handle.start_time = datetime.now().timestamp()
        mock_handle.resolved_command = Mock(command="pytest tests/")
        mock_handle.trigger_chain = ["manual", "Test"]

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_stop_tooltip("Test", mock_handle)

        assert "Trigger:" in tooltip

    def test_build_stop_tooltip_with_keyboard_shortcut(self, mock_adapter):
        """Test stop tooltip with keyboard shortcut."""
        mock_adapter.keyboard_config.shortcuts = {"Test": "1"}

        mock_handle = Mock()
        mock_handle.start_time = datetime.now().timestamp()
        mock_handle.resolved_command = Mock(command="pytest tests/")
        mock_handle.trigger_chain = []

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_stop_tooltip("Test", mock_handle)

        assert "[1] to stop" in tooltip


class TestTooltipBuilderOutputTooltip:
    """Tests for output tooltip builder."""

    def test_build_output_tooltip_no_output(self, mock_adapter):
        """Test output tooltip when no output available."""
        mock_status = Mock()
        mock_status.last_run = None

        mock_adapter.orchestrator.get_status.return_value = mock_status

        builder = TooltipBuilder(mock_adapter)
        tooltip = builder.build_output_tooltip("Test")

        assert "No output available yet" in tooltip

    def test_build_output_tooltip_with_output(self, mock_adapter):
        """Test output tooltip with available output."""
        # Create a temporary output file
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Line 1\n")
            f.write("Line 2\n")
            f.write("Line 3\n")
            f.flush()
            output_file = Path(f.name)

        try:
            mock_status = Mock()
            mock_status.last_run = Mock()
            mock_status.last_run.output_file = output_file

            mock_adapter.orchestrator.get_status.return_value = mock_status

            builder = TooltipBuilder(mock_adapter)
            tooltip = builder.build_output_tooltip("Test")

            # Tooltip format was simplified to avoid flashing
            # Now just shows command name and click hint
            assert "Test" in tooltip
            assert "Click to open in editor" in tooltip
        finally:
            output_file.unlink()

    def test_build_output_tooltip_empty_output(self, mock_adapter):
        """Test output tooltip with empty output file."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.flush()
            output_file = Path(f.name)

        try:
            mock_status = Mock()
            mock_status.last_run = Mock()
            mock_status.last_run.output_file = output_file

            mock_adapter.orchestrator.get_status.return_value = mock_status

            builder = TooltipBuilder(mock_adapter)
            tooltip = builder.build_output_tooltip("Test")

            # Tooltip format was simplified to avoid flashing
            # Empty output still shows command name and click hint
            assert "Test" in tooltip
            assert "Click to open in editor" in tooltip
        finally:
            output_file.unlink()

    def test_build_output_tooltip_running_command_with_old_output(self, mock_adapter):
        """Test that running commands don't show old output info."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6\n")
            f.flush()
            output_file = Path(f.name)

        try:
            # Setup: Command has old output in history
            mock_status = Mock()
            mock_status.last_run = Mock()
            mock_status.last_run.output_file = output_file

            mock_adapter.orchestrator.get_status.return_value = mock_status

            builder = TooltipBuilder(mock_adapter)

            # Call with is_running=True
            result = builder.build_output_tooltip("Test", is_running=True)

            # Should NOT show old file info
            assert "Command running - output will be available after completion" in result
            assert "Test" in result
            assert "[" not in result  # No line count
            assert "Click to open" not in result
        finally:
            output_file.unlink()


class TestTooltipBuilderHelpers:
    """Tests for helper methods."""

    def test_get_command_string(self, mock_adapter):
        """Test _get_command_string helper."""
        mock_preview = Mock()
        mock_preview.command = "pytest tests/ -v"
        mock_adapter.orchestrator.preview_command.return_value = mock_preview

        builder = TooltipBuilder(mock_adapter)
        result = builder._get_command_string("Test")

        assert result == "pytest tests/ -v"

    def test_get_command_string_error(self, mock_adapter):
        """Test _get_command_string with error."""
        mock_adapter.orchestrator.preview_command.side_effect = Exception("Test error")

        builder = TooltipBuilder(mock_adapter)
        result = builder._get_command_string("Test")

        assert "Error:" in result

    def test_get_downstream_commands_success(self, mock_adapter):
        """Test _get_downstream_commands for success trigger."""
        mock_adapter.orchestrator.get_trigger_graph.return_value = {"command_success:Test": ["Deploy", "Notify"]}

        builder = TooltipBuilder(mock_adapter)
        result = builder._get_downstream_commands("Test", "success")

        assert result == ["Deploy", "Notify"]

    def test_get_downstream_commands_failed(self, mock_adapter):
        """Test _get_downstream_commands for failed trigger."""
        mock_adapter.orchestrator.get_trigger_graph.return_value = {"command_failed:Test": ["Rollback"]}

        builder = TooltipBuilder(mock_adapter)
        result = builder._get_downstream_commands("Test", "failed")

        assert result == ["Rollback"]

    def test_get_downstream_commands_none(self, mock_adapter):
        """Test _get_downstream_commands with no downstream."""
        mock_adapter.orchestrator.get_trigger_graph.return_value = {}

        builder = TooltipBuilder(mock_adapter)
        result = builder._get_downstream_commands("Test", "success")

        assert result == []

    def test_get_downstream_commands_error(self, mock_adapter):
        """Test _get_downstream_commands with error."""
        mock_adapter.orchestrator.get_trigger_graph.side_effect = Exception("Test error")

        builder = TooltipBuilder(mock_adapter)
        result = builder._get_downstream_commands("Test", "success")

        assert result == []
