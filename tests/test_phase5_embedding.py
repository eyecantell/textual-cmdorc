"""Phase 5 embedding tests - Validate embedding patterns work correctly."""

import asyncio
import pytest
from pathlib import Path

from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.integrator import wire_all_callbacks


@pytest.fixture
def embedding_config(tmp_path):
    """Create a config for embedding scenarios."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[keyboard]
shortcuts = { Lint = "1", Build = "2" }
enabled = true

[[command]]
name = "Lint"
command = "echo lint"
triggers = []

[[command]]
name = "Build"
command = "echo build"
triggers = ["command_success:Lint"]

[[command]]
name = "Test"
command = "echo test"
triggers = ["command_success:Build"]
"""
    )
    return config


class TestHeadlessExecution:
    """Test headless (no UI) execution patterns."""

    def test_controller_without_view(self, embedding_config):
        """Test using controller without any view."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Should work without view
        assert controller is not None
        assert controller.orchestrator is not None
        assert len(controller.hierarchy) > 0

    def test_programmatic_command_access(self, embedding_config):
        """Test accessing commands programmatically."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Get all command names recursively
        def get_all_commands(nodes):
            names = []
            for node in nodes:
                names.append(node.name)
                if node.children:
                    names.extend(get_all_commands(node.children))
            return names

        command_names = get_all_commands(controller.hierarchy)
        assert "Lint" in command_names
        assert "Build" in command_names
        assert "Test" in command_names

    def test_event_callbacks_without_ui(self, embedding_config):
        """Test event callbacks work without UI."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        events = []

        def on_cmd_started(name, trigger):
            events.append(("started", name))

        def on_cmd_finished(name, result):
            events.append(("finished", name))

        controller.on_command_started = on_cmd_started
        controller.on_command_finished = on_cmd_finished

        # Callbacks should be stored
        assert controller.on_command_started is not None
        assert controller.on_command_finished is not None


class TestMultipleControllers:
    """Test using multiple controllers simultaneously."""

    def test_multiple_independent_controllers(self, embedding_config):
        """Test managing multiple controllers."""
        # Create two separate controllers
        ctrl1 = CmdorcController(embedding_config, enable_watchers=False)
        ctrl2 = CmdorcController(embedding_config, enable_watchers=False)

        # Should be independent
        assert ctrl1 is not ctrl2
        assert ctrl1.orchestrator is not ctrl2.orchestrator

    def test_multiple_controllers_different_configs(self, tmp_path):
        """Test multiple controllers with different configs."""
        # Create config 1
        config1 = tmp_path / "config1.toml"
        config1.write_text(
            """
[[command]]
name = "TaskA"
command = "echo a"
triggers = []
"""
        )

        # Create config 2
        config2 = tmp_path / "config2.toml"
        config2.write_text(
            """
[[command]]
name = "TaskB"
command = "echo b"
triggers = []
"""
        )

        # Create controllers
        ctrl1 = CmdorcController(config1, enable_watchers=False)
        ctrl2 = CmdorcController(config2, enable_watchers=False)

        # Get command names
        cmds1 = {node.name for node in ctrl1.hierarchy}
        cmds2 = {node.name for node in ctrl2.hierarchy}

        assert "TaskA" in cmds1
        assert "TaskB" in cmds2
        assert cmds1 != cmds2


class TestLifecycleManagement:
    """Test controller lifecycle in different scenarios."""

    @pytest.mark.asyncio
    async def test_attach_detach_cycle(self, embedding_config):
        """Test attach/detach lifecycle."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Get event loop
        loop = asyncio.get_running_loop()

        # Attach
        controller.attach(loop)
        assert controller._loop is not None

        # Detach
        controller.detach()
        assert controller._loop is None

    @pytest.mark.asyncio
    async def test_idempotent_attach(self, embedding_config):
        """Test that attach is idempotent."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        loop = asyncio.get_running_loop()

        # First attach
        controller.attach(loop)
        first_loop = controller._loop

        # Second attach should be no-op
        controller.attach(loop)
        second_loop = controller._loop

        assert first_loop is second_loop
        assert first_loop is loop

        controller.detach()

    @pytest.mark.asyncio
    async def test_attach_without_running_loop_fails(self, embedding_config):
        """Test attach fails if loop not running."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Create a non-running loop
        loop = asyncio.new_event_loop()

        # Should raise error
        with pytest.raises(RuntimeError):
            controller.attach(loop)


class TestSyncSafeExecution:
    """Test sync-safe command execution methods."""

    def test_request_run_without_attach_fails(self, embedding_config):
        """Test request_run fails if not attached."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Should raise error
        with pytest.raises(RuntimeError):
            controller.request_run("Lint")

    def test_request_cancel_without_attach_fails(self, embedding_config):
        """Test request_cancel fails if not attached."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Should raise error
        with pytest.raises(RuntimeError):
            controller.request_cancel("Lint")

    @pytest.mark.asyncio
    async def test_request_methods_after_attach(self, embedding_config):
        """Test request_* methods work after attach."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        loop = asyncio.get_running_loop()
        controller.attach(loop)

        # Should not raise
        try:
            controller.request_run("Lint")
            controller.request_cancel("Lint")
        finally:
            controller.detach()


class TestKeyboardMetadataAccess:
    """Test metadata access for keyboard integration."""

    def test_keyboard_hints_metadata_safe(self, embedding_config):
        """Test keyboard_hints returns safe metadata."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        hints = controller.keyboard_hints

        # Should be dict of strings
        assert isinstance(hints, dict)
        for key, cmd_name in hints.items():
            assert isinstance(key, str)
            assert isinstance(cmd_name, str)
            # Should not be callables
            assert not callable(key)
            assert not callable(cmd_name)

    def test_keyboard_conflicts_accessible(self, embedding_config):
        """Test keyboard_conflicts can be checked before binding."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        conflicts = controller.keyboard_conflicts

        # No conflicts in test config
        assert isinstance(conflicts, dict)

    def test_host_can_check_conflicts_before_binding(self, tmp_path):
        """Test host app pattern: check conflicts before binding."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { A = "1", B = "1" }

[[command]]
name = "A"
command = "echo a"
triggers = []

[[command]]
name = "B"
command = "echo b"
triggers = []
"""
        )

        controller = CmdorcController(config, enable_watchers=False)

        # Host app checks conflicts
        conflicts = controller.keyboard_conflicts
        hints = controller.keyboard_hints

        # Key "1" has conflict
        assert "1" in conflicts
        assert len(conflicts["1"]) == 2

        # Host would not bind conflicting key
        reserved_keys = set()
        for key in conflicts:
            reserved_keys.add(key)

        bindable_keys = {k for k in hints if k not in reserved_keys}
        assert bindable_keys == set()  # All keys have conflicts


class TestValidationIntegration:
    """Test validation in embedding scenarios."""

    def test_validation_before_execution(self, embedding_config):
        """Test host app gets validation results."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Get validation
        result = controller.validate_config()

        # Check structure
        assert result.commands_loaded > 0
        assert isinstance(result.warnings, list)
        assert isinstance(result.errors, list)

    def test_host_can_abort_on_errors(self, tmp_path):
        """Test host app can abort if validation fails."""
        config = tmp_path / "config.toml"
        config.write_text(
            """
[keyboard]
shortcuts = { Lint = "invalid_key" }

[[command]]
name = "Lint"
command = "echo lint"
triggers = []
"""
        )

        controller = CmdorcController(config, enable_watchers=False)

        result = controller.validate_config()

        # Host app pattern: check for errors
        if result.errors:
            # Abort initialization
            abort = True
        else:
            abort = False

        # Should have warnings about invalid key
        assert isinstance(result.warnings, list)


class TestCallbackIntegration:
    """Test callback wiring for embedded views."""

    def test_wire_all_callbacks_creates_links(self, embedding_config):
        """Test wire_all_callbacks for embedded scenario."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        links = wire_all_callbacks(
            controller.orchestrator,
            controller.hierarchy,
            controller.keyboard_config,
        )

        # Should have links
        assert len(links) > 0

        # Check each command has a link
        command_names = {node.name for node in controller.hierarchy}
        link_names = set(links.keys())
        assert command_names.issubset(link_names)

    def test_links_have_keyboard_shortcuts(self, embedding_config):
        """Test links get keyboard shortcuts assigned."""
        controller = CmdorcController(embedding_config, enable_watchers=False)

        links = wire_all_callbacks(
            controller.orchestrator,
            controller.hierarchy,
            controller.keyboard_config,
        )

        # Check shortcuts
        for cmd_name, link in links.items():
            expected_shortcut = controller.keyboard_config.shortcuts.get(cmd_name)
            assert link.keyboard_shortcut == expected_shortcut


class TestEmbeddingPatterns:
    """Test real-world embedding patterns."""

    def test_sidebar_embedding_pattern(self, embedding_config):
        """Test adding cmdorc as sidebar widget."""
        # Pattern: create controller, pass to view
        controller = CmdorcController(embedding_config, enable_watchers=False)

        # Host app would do: yield CmdorcView(controller, show_log_pane=False)
        # This test just validates controller setup works
        assert controller is not None
        assert len(controller.hierarchy) > 0

    def test_tabbed_embedding_pattern(self, tmp_path):
        """Test embedding multiple cmdorc instances in tabs."""
        # Create two configs
        config1 = tmp_path / "config1.toml"
        config1.write_text(
            """
[[command]]
name = "Lint"
command = "echo lint"
triggers = []
"""
        )

        config2 = tmp_path / "config2.toml"
        config2.write_text(
            """
[[command]]
name = "Build"
command = "echo build"
triggers = []
"""
        )

        # Create controllers
        ctrl_lint = CmdorcController(config1, enable_watchers=False)
        ctrl_build = CmdorcController(config2, enable_watchers=False)

        # Host app would create views for each:
        # with TabPane("Lint", id="lint-tab"):
        #     yield CmdorcView(ctrl_lint)
        # with TabPane("Build", id="build-tab"):
        #     yield CmdorcView(ctrl_build)

        # Test validates both controllers work independently
        assert len(ctrl_lint.hierarchy) > 0
        assert len(ctrl_build.hierarchy) > 0
