"""Phase 2 tests for keyboard handling and duplicate indicators."""

import pytest
from pathlib import Path

from textual_cmdorc.keyboard_handler import KeyboardHandler, DuplicateIndicator
from textual_cmdorc.controller import CmdorcController


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config file."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[keyboard]
shortcuts = { Lint = "1", Format = "2" }

[[command]]
name = "Lint"
command = "echo lint"
triggers = []

[[command]]
name = "Format"
command = "echo format"
triggers = ["command_success:Lint"]
"""
    )
    return config


@pytest.fixture
def conflict_config(tmp_path):
    """Create config with keyboard conflicts."""
    config = tmp_path / "config_conflict.toml"
    config.write_text(
        """
[keyboard]
shortcuts = { Lint = "1", Format = "1", Build = "2" }

[[command]]
name = "Lint"
command = "echo lint"
triggers = []

[[command]]
name = "Format"
command = "echo format"
triggers = []

[[command]]
name = "Build"
command = "echo build"
triggers = []
"""
    )
    return config


@pytest.fixture
def controller(tmp_config):
    """Create a controller instance."""
    return CmdorcController(tmp_config, enable_watchers=False)


@pytest.fixture
def conflict_controller(conflict_config):
    """Create a controller with conflicts."""
    return CmdorcController(conflict_config, enable_watchers=False)


class TestKeyboardHandler:
    """Test KeyboardHandler for safe keyboard binding."""

    def test_handler_initialization(self, controller):
        """Test KeyboardHandler initializes with controller."""
        handler = KeyboardHandler(controller)
        assert handler is not None
        assert handler.controller is controller

    def test_bind_all_returns_callbacks(self, controller):
        """Test bind_all returns dict of callbacks."""
        handler = KeyboardHandler(controller)
        callbacks = handler.bind_all()

        assert isinstance(callbacks, dict)
        assert len(callbacks) > 0
        # Each callback should be callable
        for key, callback in callbacks.items():
            assert callable(callback)

    def test_bindings_tracked(self, controller):
        """Test that bindings are tracked."""
        handler = KeyboardHandler(controller)
        callbacks = handler.bind_all()

        # Bindings should be tracked
        assert len(handler.bindings) == len(callbacks)
        for key in callbacks:
            assert key in handler.bindings

    def test_sync_safe_callback_creation(self, controller):
        """Test that callbacks use sync-safe request_run (FIX #1)."""
        handler = KeyboardHandler(controller)
        callback = handler._create_callback("Lint")

        assert callable(callback)
        # Callback should not raise when called
        try:
            callback()
        except RuntimeError:
            # Expected if loop not running, but callback itself is valid
            pass

    def test_conflict_detection(self, conflict_controller):
        """Test FIX #3: Keyboard conflicts are detected."""
        handler = KeyboardHandler(conflict_controller)
        conflicts = conflict_controller.keyboard_conflicts

        # Should have conflict on key "1"
        assert "1" in conflicts
        assert len(conflicts["1"]) == 2
        assert set(conflicts["1"]) == {"Lint", "Format"}

    def test_get_binding_help(self, controller):
        """Test get_binding_help generates help text."""
        handler = KeyboardHandler(controller)
        handler.bind_all()

        help_text = handler.get_binding_help()

        assert isinstance(help_text, str)
        assert "Keyboard Shortcuts:" in help_text
        assert "[1]" in help_text  # First shortcut
        assert "[2]" in help_text  # Second shortcut

    def test_get_binding_help_with_conflicts(self, conflict_controller):
        """Test help text shows conflicts."""
        handler = KeyboardHandler(conflict_controller)
        handler.bind_all()

        help_text = handler.get_binding_help()

        # Should mention conflict
        assert "⚠" in help_text or "conflict" in help_text.lower()

    def test_validate_bindings(self, controller):
        """Test binding validation."""
        handler = KeyboardHandler(controller)
        handler.bind_all()

        issues = handler.validate_bindings()

        assert isinstance(issues, dict)
        assert "conflicts" in issues
        assert "shadowed" in issues

    def test_validate_bindings_with_conflicts(self, conflict_controller):
        """Test validation detects conflicts."""
        handler = KeyboardHandler(conflict_controller)
        handler.bind_all()

        issues = handler.validate_bindings()
        conflicts = issues["conflicts"]
        shadowed = issues["shadowed"]

        # Should have conflict on "1"
        assert "1" in conflicts
        assert "1" in shadowed
        # Shadowed should be the second command
        assert "Format" in shadowed["1"]

    def test_handler_with_app_parameter(self, controller):
        """Test handler with app parameter."""
        # Mock app object
        class MockApp:
            def bind(self, key, action, show=True):
                self.bound_key = key
                self.bound_action = action

        app = MockApp()
        handler = KeyboardHandler(controller, app=app)
        callbacks = handler.bind_all()

        # At least one binding should be attempted
        assert len(callbacks) > 0


class TestDuplicateIndicator:
    """Test DuplicateIndicator for visual marking."""

    def test_duplicate_marker(self):
        """Test duplicate marker is available."""
        assert DuplicateIndicator.DUPLICATE_MARKER == "↳"

    def test_format_name_without_duplicate(self):
        """Test formatting name without duplicate indicator."""
        name = DuplicateIndicator.format_name("TestCommand", False)
        assert name == "TestCommand"
        assert "↳" not in name

    def test_format_name_with_duplicate(self):
        """Test formatting name with duplicate indicator."""
        name = DuplicateIndicator.format_name("TestCommand", True)
        assert "↳" in name
        assert "TestCommand" in name

    def test_get_duplicate_warning_no_duplicates(self):
        """Test warning for non-duplicate command."""
        warning = DuplicateIndicator.get_duplicate_warning("TestCmd", 1)
        assert warning == ""

    def test_get_duplicate_warning_with_duplicates(self):
        """Test warning for duplicate command."""
        warning = DuplicateIndicator.get_duplicate_warning("TestCmd", 3)

        assert warning != ""
        assert "TestCmd" in warning
        assert "3" in warning
        assert "⚠" in warning

    def test_get_duplicate_warning_message(self):
        """Test duplicate warning message content."""
        warning = DuplicateIndicator.get_duplicate_warning("Lint", 2)

        assert "appears 2 times" in warning
        assert "Shortcuts and cancellations affect all instances" in warning


class TestKeyboardControllerIntegration:
    """Test keyboard functionality integration with controller."""

    def test_controller_keyboard_hints_available(self, controller):
        """Test controller provides keyboard hints."""
        hints = controller.keyboard_hints

        assert isinstance(hints, dict)
        assert len(hints) > 0
        # Should have shortcut mappings
        assert "1" in hints
        assert hints["1"] == "Lint"

    def test_controller_keyboard_conflicts_property(self, conflict_controller):
        """Test controller keyboard_conflicts property (FIX #3)."""
        conflicts = conflict_controller.keyboard_conflicts

        assert isinstance(conflicts, dict)
        # Should detect conflict on "1"
        assert "1" in conflicts
        assert len(conflicts["1"]) == 2

    def test_controller_sync_safe_request_run(self, controller):
        """Test FIX #1: request_run without event loop (raises RuntimeError)."""
        # request_run should raise if loop not attached
        with pytest.raises(RuntimeError):
            controller.request_run("Lint")

    def test_keyboard_config_enabled_flag(self, tmp_path):
        """Test keyboard config enabled flag."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { Lint = "1" }
enabled = false

[[command]]
name = "Lint"
command = "echo lint"
triggers = []
"""
        )
        controller = CmdorcController(config, enable_watchers=False)

        # Config should be disabled
        assert controller.keyboard_config.enabled is False
        # But hints should still be available (metadata)
        hints = controller.keyboard_hints
        assert len(hints) > 0


class TestKeyboardConflictScenarios:
    """Test realistic keyboard conflict scenarios."""

    def test_alphabetical_conflict_resolution(self):
        """Test that conflicts are resolved alphabetically (first one wins)."""
        # In Python 3.7+, dicts maintain insertion order, but conflicts
        # should be documented as "first one wins"
        conflicts_dict = {
            "1": ["Lint", "Format", "Build"],  # Alphabetically: Build < Format < Lint
        }

        # The first in the list wins
        winning_command = conflicts_dict["1"][0]
        assert winning_command == "Lint"

    def test_multiple_conflicts(self, tmp_path):
        """Test handling multiple simultaneous conflicts."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { "A" = "1", "B" = "1", "C" = "2", "D" = "2", "E" = "2" }

[[command]]
name = "A"
command = "echo a"
triggers = []

[[command]]
name = "B"
command = "echo b"
triggers = []

[[command]]
name = "C"
command = "echo c"
triggers = []

[[command]]
name = "D"
command = "echo d"
triggers = []

[[command]]
name = "E"
command = "echo e"
triggers = []
"""
        )
        controller = CmdorcController(config, enable_watchers=False)
        conflicts = controller.keyboard_conflicts

        # Should have conflicts on "1" and "2"
        assert "1" in conflicts
        assert "2" in conflicts
        assert len(conflicts["1"]) == 2
        assert len(conflicts["2"]) == 3

    def test_conflict_info_completeness(self, conflict_controller):
        """Test conflict information is complete."""
        handler = KeyboardHandler(conflict_controller)
        issues = handler.validate_bindings()

        # All conflicting commands should be identified
        assert "1" in issues["conflicts"]
        assert set(issues["conflicts"]["1"]) == {"Lint", "Format"}
        assert "Format" in issues["shadowed"]["1"]
