"""Integration tests for CommandLink output file path updates.

These tests use the real textual-filelink library (not mocks) to verify
that the bug fix for updating FileLink paths works correctly.

Regression test for: https://github.com/eyecantell/textual-cmdorc/issues/XXX
Output file links not updating when commands run multiple times.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Mock cmdorc before importing textual-filelink
from conftest import CommandOrchestrator, RunHandle, RunnerConfig, load_config

cmdorc_module = Mock()
cmdorc_module.RunHandle = RunHandle
cmdorc_module.CommandOrchestrator = CommandOrchestrator
cmdorc_module.RunnerConfig = RunnerConfig
cmdorc_module.load_config = load_config
sys.modules["cmdorc"] = cmdorc_module

# Force reimport of the REAL textual-filelink (remove any mocks)
if "textual_filelink" in sys.modules:
    del sys.modules["textual_filelink"]
if "textual_filelink.command_link" in sys.modules:
    del sys.modules["textual_filelink.command_link"]
if "textual_filelink.file_link" in sys.modules:
    del sys.modules["textual_filelink.file_link"]

# Now import the REAL textual-filelink (not mocked)
from textual_filelink import CommandLink, FileLink

# Verify we got the real thing, not a mock
# Check if CommandLink has the real __init__ signature
try:
    import inspect

    sig = inspect.signature(CommandLink.__init__)
    params = list(sig.parameters.keys())
    if "command_name" not in params:
        pytest.skip("textual_filelink is mocked, skipping integration tests", allow_module_level=True)
except Exception:
    pytest.skip("Cannot verify textual_filelink, skipping integration tests", allow_module_level=True)


class TestCommandLinkOutputPathUpdates:
    """Test that CommandLink.set_output_path() correctly updates FileLink paths."""

    def test_set_output_path_updates_existing_filelink(self, tmp_path):
        """Regression test: set_output_path() should update existing FileLink, not ignore it.

        This is the core bug fix test. Previously, when a CommandLink was initialized
        with an output_path (making _name_widget a FileLink), calling set_output_path()
        with a new path would do nothing because the condition checked for Static widgets.

        Now it should call FileLink.set_path() to update the existing FileLink.
        """
        # Create two different output files
        output_file_1 = tmp_path / "run1_output.txt"
        output_file_2 = tmp_path / "run2_output.txt"
        output_file_1.write_text("First run output")
        output_file_2.write_text("Second run output")

        # Create CommandLink with initial output_path
        # This makes _name_widget a FileLink pointing to output_file_1
        link = CommandLink(
            command_name="TestCommand",
            output_path=output_file_1,
            initial_status_icon="◯",
        )

        # Verify initial state: _name_widget is a FileLink
        assert isinstance(link._name_widget, FileLink), "Expected _name_widget to be FileLink"
        assert link._name_widget._path == output_file_1.resolve(), "Expected initial path to be output_file_1"

        # Store reference to original widget to verify it's updated (not replaced)
        original_widget = link._name_widget
        original_widget_id = id(original_widget)

        # Now update to a new output path (simulating a new command run)
        link.set_output_path(output_file_2)

        # Verify the fix: FileLink should be updated, not replaced
        assert isinstance(link._name_widget, FileLink), "Expected _name_widget to still be FileLink"
        assert id(link._name_widget) == original_widget_id, "Expected same widget instance (updated, not replaced)"
        assert link._name_widget._path == output_file_2.resolve(), "Expected path updated to output_file_2"
        assert link._output_path == output_file_2.resolve(), "Expected _output_path updated to output_file_2"

    @pytest.mark.skip(reason="Requires mounted Textual app for widget.remove()")
    def test_set_output_path_creates_filelink_from_static(self):
        """Test that set_output_path() creates FileLink when starting with Static (no initial path).

        Note: This test requires a mounted Textual app context and is tested via
        the full app tests in test_cmdorc_app.py instead.
        """
        # Create CommandLink without output_path
        # This makes _name_widget a Static widget
        link = CommandLink(
            command_name="TestCommand",
            output_path=None,
            initial_status_icon="◯",
        )

        # Verify initial state: _name_widget is Static
        from textual.widgets import Static

        assert isinstance(link._name_widget, Static), "Expected _name_widget to be Static"
        assert not isinstance(link._name_widget, FileLink), "Expected _name_widget NOT to be FileLink"

        # Now set an output path
        output_file = Path("/tmp/test_output.txt")
        link.set_output_path(output_file)

        # Verify FileLink was created
        assert isinstance(link._name_widget, FileLink), "Expected _name_widget to become FileLink"
        assert link._name_widget._path == output_file.resolve(), "Expected path set to output_file"
        assert link._output_path == output_file.resolve(), "Expected _output_path set to output_file"

    @pytest.mark.skip(reason="Requires mounted Textual app for widget.remove()")
    def test_set_output_path_removes_filelink_when_set_to_none(self, tmp_path):
        """Test that set_output_path(None) converts FileLink back to Static.

        Note: This test requires a mounted Textual app context and is tested via
        the full app tests in test_cmdorc_app.py instead.
        """
        # Create CommandLink with output_path
        output_file = tmp_path / "output.txt"
        output_file.write_text("test")

        link = CommandLink(
            command_name="TestCommand",
            output_path=output_file,
            initial_status_icon="◯",
        )

        # Verify FileLink exists
        assert isinstance(link._name_widget, FileLink), "Expected _name_widget to be FileLink"

        # Clear the output path
        link.set_output_path(None)

        # Verify FileLink was replaced with Static
        from textual.widgets import Static

        assert isinstance(link._name_widget, Static), "Expected _name_widget to be Static"
        assert not isinstance(link._name_widget, FileLink), "Expected _name_widget NOT to be FileLink"
        assert link._output_path is None, "Expected _output_path to be None"

    def test_multiple_output_path_updates(self, tmp_path):
        """Test multiple successive path updates (simulating multiple command runs)."""
        # Create multiple output files
        outputs = [tmp_path / f"run{i}_output.txt" for i in range(3)]
        for output in outputs:
            output.write_text(f"Run {outputs.index(output)} output")

        # Start with first output
        link = CommandLink(
            command_name="TestCommand",
            output_path=outputs[0],
            initial_status_icon="◯",
        )

        # Verify initial state
        assert link._name_widget._path == outputs[0].resolve()
        original_widget_id = id(link._name_widget)

        # Update to second output
        link.set_output_path(outputs[1])
        assert link._name_widget._path == outputs[1].resolve()
        assert id(link._name_widget) == original_widget_id, "Widget should be updated, not replaced"

        # Update to third output
        link.set_output_path(outputs[2])
        assert link._name_widget._path == outputs[2].resolve()
        assert id(link._name_widget) == original_widget_id, "Widget should be updated, not replaced"

    def test_filelink_set_path_method_exists(self):
        """Verify that FileLink.set_path() method exists (required for the fix)."""
        assert hasattr(FileLink, "set_path"), "FileLink must have set_path() method"

        # Verify signature
        import inspect

        sig = inspect.signature(FileLink.set_path)
        params = list(sig.parameters.keys())

        assert "path" in params, "set_path() must accept 'path' parameter"
        assert "display_name" in params, "set_path() must accept 'display_name' parameter"


# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration
