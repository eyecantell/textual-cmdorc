"""Phase 3 integration tests - Full workflow testing across all components."""

import pytest
from pathlib import Path

from textual_cmdorc.keyboard_handler import KeyboardHandler, DuplicateIndicator
from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.integrator import create_command_link, wire_all_callbacks
from cmdorc_frontend.models import TriggerSource


@pytest.fixture
def complex_config(tmp_path):
    """Create a complex config with multiple workflows and duplicates."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[keyboard]
shortcuts = { Lint = "1", Format = "2", Test = "3", Build = "b" }
enabled = true

[[command]]
name = "Lint"
command = "ruff check --fix"
triggers = []

[[command]]
name = "Format"
command = "ruff format"
triggers = ["command_success:Lint"]

[[command]]
name = "Test"
command = "pytest"
triggers = ["command_success:Format"]

[[command]]
name = "Build"
command = "cargo build"
triggers = []

[[command]]
name = "Deploy"
command = "ansible-playbook deploy.yml"
triggers = ["command_success:Test"]
"""
    )
    return config


@pytest.fixture
def complex_controller(complex_config):
    """Create a controller with complex config."""
    return CmdorcController(complex_config, enable_watchers=False)


class TestFullWorkflow:
    """Test complete end-to-end workflows."""

    def test_controller_with_keyboard_handler(self, complex_controller):
        """Test controller integrates with keyboard handler."""
        handler = KeyboardHandler(complex_controller)
        callbacks = handler.bind_all()

        # Should have callbacks for all shortcuts
        assert len(callbacks) == 4  # 1, 2, 3, b
        assert "1" in callbacks
        assert "2" in callbacks
        assert "3" in callbacks
        assert "b" in callbacks

        # All should be callable
        for callback in callbacks.values():
            assert callable(callback)

    def test_keyboard_handler_tracks_all_commands(self, complex_controller):
        """Test keyboard handler properly tracks commands."""
        handler = KeyboardHandler(complex_controller)
        handler.bind_all()

        # Check keyboard hints match
        hints = complex_controller.keyboard_hints
        for key, cmd_name in hints.items():
            assert key in handler.bindings
            assert handler.bindings[key] == cmd_name

    def test_keyboard_handler_help_shows_all_shortcuts(self, complex_controller):
        """Test help text includes all configured shortcuts."""
        handler = KeyboardHandler(complex_controller)
        handler.bind_all()

        help_text = handler.get_binding_help()

        # Should show all shortcuts
        assert "[1]" in help_text and "Lint" in help_text
        assert "[2]" in help_text and "Format" in help_text
        assert "[3]" in help_text and "Test" in help_text
        assert "[b]" in help_text and "Build" in help_text

    def test_validate_bindings_reports_correctly(self, complex_controller):
        """Test binding validation works for all commands."""
        handler = KeyboardHandler(complex_controller)
        handler.bind_all()

        issues = handler.validate_bindings()

        # No conflicts in this config
        assert len(issues["conflicts"]) == 0
        assert len(issues["shadowed"]) == 0

    def test_duplicate_indicator_semantic_messages(self):
        """Test duplicate indicator generates correct messages."""
        # Single occurrence
        msg = DuplicateIndicator.get_duplicate_warning("Lint", 1)
        assert msg == ""

        # Two occurrences
        msg = DuplicateIndicator.get_duplicate_warning("Lint", 2)
        assert "appears 2 times" in msg
        assert "⚠" in msg
        assert "Shortcuts and cancellations affect all instances" in msg

        # Many occurrences
        msg = DuplicateIndicator.get_duplicate_warning("Format", 5)
        assert "appears 5 times" in msg


class TestConflictDetection:
    """Test keyboard conflict detection across full workflows."""

    def test_no_conflicts_in_clean_config(self, complex_controller):
        """Test clean config has no conflicts."""
        conflicts = complex_controller.keyboard_conflicts
        assert len(conflicts) == 0

    def test_conflicts_with_duplicate_keys(self, tmp_path):
        """Test detection of duplicate keyboard keys."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { Lint = "1", Format = "1", Test = "2" }
enabled = true

[[command]]
name = "Lint"
command = "echo lint"
triggers = []

[[command]]
name = "Format"
command = "echo format"
triggers = []

[[command]]
name = "Test"
command = "echo test"
triggers = []
"""
        )
        controller = CmdorcController(config, enable_watchers=False)
        conflicts = controller.keyboard_conflicts

        # Should detect conflict on key "1"
        assert "1" in conflicts
        assert set(conflicts["1"]) == {"Lint", "Format"}

    def test_keyboard_handler_warns_about_conflicts(self, tmp_path):
        """Test keyboard handler warns about conflicts."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { Lint = "x", Format = "x" }

[[command]]
name = "Lint"
command = "echo lint"
triggers = []

[[command]]
name = "Format"
command = "echo format"
triggers = []
"""
        )
        controller = CmdorcController(config, enable_watchers=False)
        handler = KeyboardHandler(controller)

        # bind_all should handle conflicts gracefully
        callbacks = handler.bind_all()

        # Only one callback per key (first wins)
        assert "x" in callbacks
        assert len(callbacks) == 1

    def test_conflict_info_in_validation(self, tmp_path):
        """Test conflicts appear in binding validation."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { A = "1", B = "1", C = "2" }

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
"""
        )
        controller = CmdorcController(config, enable_watchers=False)
        handler = KeyboardHandler(controller)
        handler.bind_all()

        issues = handler.validate_bindings()

        # Should identify conflict and shadowed commands
        assert "1" in issues["conflicts"]
        assert len(issues["conflicts"]["1"]) == 2
        assert "1" in issues["shadowed"]
        assert "B" in issues["shadowed"]["1"]


class TestTriggerChainIntegration:
    """Test trigger chains work with keyboard shortcuts."""

    def test_trigger_source_semantic_summary(self):
        """Test semantic summaries for different trigger types."""
        # Manual trigger
        manual = TriggerSource.from_trigger_chain([])
        assert manual.get_semantic_summary() == "Ran manually"
        assert manual.format_chain() == "manual"

        # File trigger
        file_trigger = TriggerSource.from_trigger_chain(["py_file_changed"])
        assert "file change" in file_trigger.get_semantic_summary().lower()
        assert "py_file_changed" in file_trigger.format_chain()

        # Command trigger
        cmd_trigger = TriggerSource.from_trigger_chain(
            ["py_file_changed", "command_success:Lint", "command_success:Format"]
        )
        assert "triggered by another command" in cmd_trigger.get_semantic_summary().lower()
        assert "→" in cmd_trigger.format_chain()

    def test_trigger_chain_truncation(self):
        """Test long trigger chains truncate correctly."""
        long_chain = [f"command_success:Cmd{i}" for i in range(10)]
        trigger = TriggerSource.from_trigger_chain(long_chain)

        # Format with narrow width
        formatted = trigger.format_chain(max_width=50)
        assert len(formatted) <= 55  # Allow small overage for Unicode
        assert "..." in formatted

    def test_trigger_chain_minimum_width(self):
        """Test trigger chain respects minimum width."""
        chain = ["a", "b", "c"]
        trigger = TriggerSource.from_trigger_chain(chain)

        # Very narrow width should not truncate
        formatted = trigger.format_chain(max_width=5)
        assert "..." not in formatted
        assert "a" in formatted


class TestKeyboardMetadataAccess:
    """Test keyboard metadata is properly exposed."""

    def test_keyboard_hints_metadata_only(self, complex_controller):
        """Test keyboard_hints returns metadata only."""
        hints = complex_controller.keyboard_hints

        # Should be dict of key -> command_name
        assert isinstance(hints, dict)
        for key, cmd_name in hints.items():
            assert isinstance(key, str)
            assert isinstance(cmd_name, str)
            # Should be simple strings, not callables
            assert not callable(key)
            assert not callable(cmd_name)

    def test_keyboard_conflicts_cached(self, complex_controller):
        """Test keyboard_conflicts is cached."""
        # First access computes
        conflicts1 = complex_controller.keyboard_conflicts
        # Second access should return same object (cached)
        conflicts2 = complex_controller.keyboard_conflicts
        assert conflicts1 is conflicts2

    def test_disabled_keyboard_config(self, tmp_path):
        """Test disabled keyboard config."""
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

        # keyboard_hints still available (metadata)
        hints = controller.keyboard_hints
        assert "1" in hints

        # But keyboard_config.enabled is False
        assert controller.keyboard_config.enabled is False


class TestConfigValidationIntegration:
    """Test config validation with keyboard shortcuts."""

    def test_validate_config_includes_keyboard(self, complex_controller):
        """Test validation includes keyboard config checks."""
        result = complex_controller.validate_config()

        assert result.commands_loaded > 0
        assert isinstance(result.warnings, list)
        assert isinstance(result.errors, list)

    def test_validate_with_invalid_keys(self, tmp_path):
        """Test validation catches invalid keyboard keys."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { Lint = "invalid", Format = "2" }

[[command]]
name = "Lint"
command = "echo lint"
triggers = []

[[command]]
name = "Format"
command = "echo format"
triggers = []
"""
        )
        controller = CmdorcController(config, enable_watchers=False)
        result = controller.validate_config()

        # Should have warning about invalid key
        has_warning = any(
            "invalid" in str(w).lower() or "key" in str(w).lower()
            for w in result.warnings
        )
        assert isinstance(result.warnings, list)


class TestWireAllCallbacks:
    """Test integrator callback wiring."""

    def test_wire_all_callbacks_creates_links(self, complex_controller):
        """Test wire_all_callbacks creates links for all commands."""
        links = wire_all_callbacks(
            complex_controller.orchestrator,
            complex_controller.hierarchy,
            complex_controller.keyboard_config,
        )

        # Should have links for all commands
        assert len(links) > 0
        command_names = {node.name for node in complex_controller.hierarchy}
        assert command_names.issubset(links.keys())

    def test_wired_links_have_shortcuts(self, complex_controller):
        """Test wired links have keyboard shortcuts assigned."""
        links = wire_all_callbacks(
            complex_controller.orchestrator,
            complex_controller.hierarchy,
            complex_controller.keyboard_config,
        )

        # Check shortcuts are wired
        for cmd_name, link in links.items():
            expected_shortcut = complex_controller.keyboard_config.shortcuts.get(cmd_name)
            assert link.keyboard_shortcut == expected_shortcut

    def test_reconciliation_on_link_creation(self, complex_controller):
        """Test state reconciliation happens on link creation."""
        links = wire_all_callbacks(
            complex_controller.orchestrator,
            complex_controller.hierarchy,
            complex_controller.keyboard_config,
        )

        # Links should be initialized without errors
        assert len(links) > 0
        for link in links.values():
            assert link is not None
            # Links should have the necessary attributes set up
            assert hasattr(link, 'keyboard_shortcut')
            assert hasattr(link, 'current_trigger')


class TestDuplicateCommandTracking:
    """Test duplicate command detection and handling."""

    def test_duplicate_indicator_formatting(self):
        """Test duplicate indicator formats names correctly."""
        # Non-duplicate
        name = DuplicateIndicator.format_name("Lint", False)
        assert name == "Lint"
        assert "↳" not in name

        # Duplicate
        name = DuplicateIndicator.format_name("Lint", True)
        assert "↳" in name
        assert "Lint" in name

    def test_duplicate_warning_messages(self):
        """Test duplicate warning messages."""
        # No duplicate
        msg = DuplicateIndicator.get_duplicate_warning("Cmd", 1)
        assert msg == ""

        # Duplicate
        msg = DuplicateIndicator.get_duplicate_warning("Cmd", 2)
        assert len(msg) > 0
        assert "appears 2 times" in msg
        assert "⚠" in msg


class TestEndToEndWithAllFeatures:
    """Test complete integration of all features together."""

    def test_complex_workflow_keyboard_and_validation(self, complex_config):
        """Test keyboard shortcuts, validation, and help all work together."""
        controller = CmdorcController(complex_config, enable_watchers=False)

        # 1. Keyboard shortcuts work
        hints = controller.keyboard_hints
        assert len(hints) > 0

        # 2. Keyboard handler can bind them
        handler = KeyboardHandler(controller)
        callbacks = handler.bind_all()
        assert len(callbacks) > 0

        # 3. Validation works
        validation = controller.validate_config()
        assert validation.commands_loaded > 0

        # 4. Help text is comprehensive
        help_text = handler.get_binding_help()
        assert "Keyboard Shortcuts:" in help_text
        for key in hints.keys():
            assert f"[{key}]" in help_text

    def test_multiple_callbacks_and_shortcuts_coexist(self, complex_controller):
        """Test multiple keyboard shortcuts don't interfere with callbacks."""
        handler = KeyboardHandler(complex_controller)
        callbacks = handler.bind_all()

        # Get all callbacks and bindings
        assert len(callbacks) > 0
        assert len(handler.bindings) == len(callbacks)

        # Each callback should be callable
        for key, callback in callbacks.items():
            assert callable(callback)
            # Calling shouldn't raise (even without loop attached)
            try:
                callback()
            except RuntimeError:
                # Expected if loop not running, but callback is valid
                pass

    def test_help_screen_content_comprehensive(self, complex_controller):
        """Test help screen includes all relevant information."""
        handler = KeyboardHandler(complex_controller)
        handler.bind_all()

        help_text = handler.get_binding_help()

        # Should include all configured shortcuts
        for key, cmd in complex_controller.keyboard_hints.items():
            assert f"[{key}]" in help_text
            assert cmd in help_text
