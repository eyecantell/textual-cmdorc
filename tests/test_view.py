"""Tests for CmdorcView - Phase 0 architecture."""

from pathlib import Path

import pytest

from cmdorc_frontend.models import PresentationUpdate, TriggerSource
from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.view import CmdorcView


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
def controller(tmp_config):
    """Create a controller instance."""
    return CmdorcController(tmp_config, enable_watchers=False)


def test_view_initialization(controller):
    """Test view initializes with controller."""
    view = CmdorcView(controller, show_log_pane=True, enable_local_bindings=False)
    assert view is not None
    assert view.controller is controller
    assert view.show_log_pane is True
    assert view.enable_local_bindings is False


def test_view_initialization_no_log_pane(controller):
    """Test view can be initialized without log pane."""
    view = CmdorcView(controller, show_log_pane=False)
    assert view.show_log_pane is False


def test_view_duplicate_tracking_initialization(controller):
    """Test FIX #2: View initializes duplicate tracking."""
    view = CmdorcView(controller)
    assert isinstance(view._command_links, dict)
    assert len(view._command_links) == 0  # Empty before tree built


def test_view_duplicate_tracking_structure(controller):
    """Test FIX #2: _command_links tracks all instances per command."""
    view = CmdorcView(controller)
    # Simulate building tree with duplicates
    view._command_links["TestCmd"] = []
    view._command_links["TestCmd"].append("link1")
    view._command_links["TestCmd"].append("link2")

    assert len(view._command_links["TestCmd"]) == 2


def test_view_command_links_empty_after_init(controller):
    """Test command links are empty after initialization."""
    view = CmdorcView(controller)
    assert view._command_links == {}


def test_view_hierarchy_from_controller(controller):
    """Test view can access controller hierarchy."""
    CmdorcView(controller)
    hierarchy = controller.hierarchy
    assert len(hierarchy) > 0
    assert "Lint" in [node.name for node in hierarchy]


def test_view_keyboard_config_access(controller):
    """Test view can access controller keyboard config."""
    CmdorcView(controller)
    keyboard_config = controller.keyboard_config
    assert keyboard_config.enabled is True
    assert "Lint" in keyboard_config.shortcuts
    assert keyboard_config.shortcuts["Lint"] == "1"


def test_view_keyboard_hints_access(controller):
    """Test view can access controller keyboard hints (POLISH #1)."""
    CmdorcView(controller)
    hints = controller.keyboard_hints
    assert "1" in hints
    assert hints["1"] == "Lint"
    assert "2" in hints
    assert hints["2"] == "Format"


def test_view_update_command_with_single_instance(controller):
    """Test updating command display."""
    view = CmdorcView(controller)

    # Create a mock link
    class MockLink:
        def apply_update(self, update):
            self.last_update = update

    mock_link = MockLink()
    view._command_links["TestCmd"] = [mock_link]

    # Create update
    update = PresentationUpdate(
        icon="✅",
        running=False,
        tooltip="Test completed",
        output_path=Path("/tmp/test.log"),
    )

    # Apply update
    view.update_command("TestCmd", update)
    assert mock_link.last_update is update


def test_view_update_command_with_duplicates(controller):
    """Test FIX #2: Updating duplicates updates all instances."""
    view = CmdorcView(controller)

    # Create mock links for duplicate command
    class MockLink:
        def __init__(self):
            self.last_update = None

        def apply_update(self, update):
            self.last_update = update

    link1 = MockLink()
    link2 = MockLink()
    view._command_links["DuplicateCmd"] = [link1, link2]

    # Create update
    update = PresentationUpdate(
        icon="⏳",
        running=True,
        tooltip="Running...",
    )

    # Apply update
    view.update_command("DuplicateCmd", update)

    # Both should receive update
    assert link1.last_update is update
    assert link2.last_update is update


def test_view_update_nonexistent_command(controller):
    """Test updating nonexistent command doesn't crash."""
    view = CmdorcView(controller)

    update = PresentationUpdate(
        icon="❓",
        running=False,
        tooltip="Not found",
    )

    # Should not raise
    view.update_command("NonexistentCmd", update)


def test_view_duplicate_detection_logic(controller):
    """Test duplicate detection in build_tree."""
    view = CmdorcView(controller)

    # Manually test the duplicate detection logic
    view._command_links["Cmd1"] = []
    occurrence_count = len(view._command_links.get("Cmd1", []))
    is_duplicate_1 = occurrence_count > 0
    assert is_duplicate_1 is False

    # Add first instance
    view._command_links["Cmd1"].append("link1")

    # Check for second instance
    occurrence_count = len(view._command_links.get("Cmd1", []))
    is_duplicate_2 = occurrence_count > 0
    assert is_duplicate_2 is True


def test_view_clear_command_links(controller):
    """Test clearing command links."""
    view = CmdorcView(controller)

    # Populate
    view._command_links["Cmd1"] = ["link1"]
    view._command_links["Cmd2"] = ["link2", "link3"]
    assert len(view._command_links) == 2

    # Clear
    view._command_links.clear()
    assert len(view._command_links) == 0


def test_view_composition_with_log_pane(controller):
    """Test view composes tree and log pane when enabled."""
    view = CmdorcView(controller, show_log_pane=True)
    # Composition is checked during on_mount, which requires Textual test utils
    # This test just verifies the flag is set correctly
    assert view.show_log_pane is True


def test_view_composition_without_log_pane(controller):
    """Test view composes tree without log pane when disabled."""
    view = CmdorcView(controller, show_log_pane=False)
    assert view.show_log_pane is False


def test_view_keyboard_shortcut_from_config(controller):
    """Test view can extract keyboard shortcut from config."""
    CmdorcView(controller)

    # Simulate what build_tree does
    node_name = "Lint"
    shortcut = controller.keyboard_config.shortcuts.get(node_name) if controller.keyboard_config.enabled else None

    assert shortcut == "1"


def test_view_keyboard_shortcut_disabled(tmp_path):
    """Test view respects disabled keyboard config."""
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
    CmdorcView(controller)

    # When disabled, shortcut should be None
    node_name = "Lint"
    shortcut = controller.keyboard_config.shortcuts.get(node_name) if controller.keyboard_config.enabled else None

    assert shortcut is None


def test_view_respects_controller_hierarchy(controller):
    """Test view respects the controller's command hierarchy."""
    CmdorcView(controller)

    hierarchy = controller.hierarchy
    assert len(hierarchy) >= 1

    # Check that hierarchy contains expected commands
    command_names = [node.name for node in hierarchy]
    assert "Lint" in command_names


def test_view_multiple_instances_same_controller(controller):
    """Test multiple views can use same controller."""
    view1 = CmdorcView(controller, show_log_pane=True)
    view2 = CmdorcView(controller, show_log_pane=False)

    assert view1.controller is view2.controller
    assert view1.controller is controller
    assert view1.show_log_pane is True
    assert view2.show_log_pane is False


def test_view_duplicate_marker_logic(controller):
    """Test FIX #2: duplicate marker detection."""
    view = CmdorcView(controller)

    # Test case: first occurrence should not be marked duplicate
    view._command_links["Cmd"] = []
    is_duplicate_first = len(view._command_links.get("Cmd", [])) > 0
    assert is_duplicate_first is False

    # Add link
    view._command_links["Cmd"].append("link1")

    # Test case: second occurrence should be marked duplicate
    is_duplicate_second = len(view._command_links.get("Cmd", [])) > 0
    assert is_duplicate_second is True


def test_view_keyboard_conflicts_visibility(controller):
    """Test view can access keyboard conflicts from controller."""
    CmdorcView(controller)
    conflicts = controller.keyboard_conflicts

    # This config shouldn't have conflicts (each key is unique)
    assert isinstance(conflicts, dict)


def test_view_initialization_preserves_controller_settings(controller):
    """Test view initialization doesn't mutate controller."""
    original_loop = controller._loop
    original_hierarchy_len = len(controller.hierarchy)

    CmdorcView(controller)

    # Controller should be unchanged
    assert controller._loop is original_loop
    assert len(controller.hierarchy) == original_hierarchy_len


def test_view_trigger_source_compatibility(controller):
    """Test view can work with TriggerSource updates."""
    CmdorcView(controller)

    # Create a trigger source
    trigger = TriggerSource.from_trigger_chain(["file_changed", "command_success:Lint"])
    assert trigger.name == "command_success:Lint"
    assert trigger.kind == "lifecycle"
    assert len(trigger.chain) == 2

    # Verify semantic summary works
    semantic = trigger.get_semantic_summary()
    assert "automatically" in semantic.lower()
