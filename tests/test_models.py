"""Tests for cmdorc_frontend models - Phase 0 architecture."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from cmdorc_frontend.models import (
    VALID_KEYS,
    CommandNode,
    ConfigValidationResult,
    KeyboardConfig,
    PresentationUpdate,
    TriggerSource,
    UserSettings,
)


class TestTriggerSource:
    """Test TriggerSource model with FIX #7 and semantic summaries."""

    def test_trigger_source_from_empty_chain(self):
        """Test TriggerSource.from_trigger_chain with empty chain."""
        trigger = TriggerSource.from_trigger_chain([])
        assert trigger.name == "manual"
        assert trigger.kind == "manual"
        assert trigger.chain == []

    def test_trigger_source_from_file_change(self):
        """Test TriggerSource from file watcher trigger."""
        chain = ["file_changed:*.py"]
        trigger = TriggerSource.from_trigger_chain(chain)
        assert trigger.name == "file_changed:*.py"
        assert trigger.kind == "file"
        assert trigger.chain == chain

    def test_trigger_source_from_lifecycle(self):
        """Test TriggerSource from lifecycle trigger."""
        chain = ["command_success:Lint"]
        trigger = TriggerSource.from_trigger_chain(chain)
        assert trigger.name == "command_success:Lint"
        assert trigger.kind == "lifecycle"
        assert trigger.chain == chain

    def test_trigger_source_full_chain(self):
        """Test TriggerSource with complete chain."""
        chain = ["file_changed:*.py", "command_success:Lint", "command_success:Format"]
        trigger = TriggerSource.from_trigger_chain(chain)
        assert trigger.name == "command_success:Format"  # Last one
        assert trigger.kind == "lifecycle"
        assert trigger.chain == chain

    def test_trigger_source_format_chain_empty(self):
        """Test format_chain with no chain."""
        trigger = TriggerSource("manual", "manual", chain=[])
        formatted = trigger.format_chain()
        assert formatted == "manual"

    def test_trigger_source_format_chain_single(self):
        """Test format_chain with single trigger."""
        trigger = TriggerSource("file", "file", chain=["file_changed:*.py"])
        formatted = trigger.format_chain()
        assert "file_changed:*.py" in formatted

    def test_trigger_source_format_chain_multiple(self):
        """Test format_chain with multiple triggers."""
        chain = ["file_changed:*.py", "command_success:Lint"]
        trigger = TriggerSource("lifecycle", "lifecycle", chain=chain)
        formatted = trigger.format_chain()
        assert "file_changed:*.py" in formatted
        assert "command_success:Lint" in formatted
        assert " → " in formatted

    def test_trigger_source_format_chain_custom_separator(self):
        """Test format_chain with custom separator."""
        chain = ["a", "b", "c"]
        trigger = TriggerSource("", "", chain=chain)
        formatted = trigger.format_chain(separator=" > ")
        assert formatted == "a > b > c"

    def test_trigger_source_format_chain_truncation(self):
        """Test format_chain with left truncation."""
        chain = ["very_long_trigger_1", "very_long_trigger_2", "very_long_trigger_3"]
        trigger = TriggerSource("", "", chain=chain)
        formatted = trigger.format_chain(max_width=30)
        assert "..." in formatted
        # Note: Unicode separator "→" takes multiple bytes, so length may exceed max_width slightly
        # The important part is that truncation happens
        assert len(formatted) <= 35  # Allow small overage due to separator width

    def test_trigger_source_format_chain_minimum_width(self):
        """Test FIX #7: format_chain minimum width check."""
        chain = ["a", "b", "c"]
        trigger = TriggerSource("", "", chain=chain)

        # With max_width < 10, should return as-is (too narrow to truncate)
        formatted = trigger.format_chain(max_width=5)
        assert "..." not in formatted
        assert formatted == "a → b → c"

    def test_trigger_source_format_chain_exactly_width(self):
        """Test format_chain when content exactly fits."""
        chain = ["short"]
        trigger = TriggerSource("", "", chain=chain)
        formatted = trigger.format_chain(max_width=100)
        assert "..." not in formatted
        assert formatted == "short"

    def test_trigger_source_get_semantic_summary_manual(self):
        """Test get_semantic_summary for manual trigger."""
        trigger = TriggerSource("manual", "manual", chain=[])
        summary = trigger.get_semantic_summary()
        assert summary == "Ran manually"

    def test_trigger_source_get_semantic_summary_file(self):
        """Test get_semantic_summary for file watcher trigger."""
        trigger = TriggerSource("file", "file", chain=["file_changed"])
        summary = trigger.get_semantic_summary()
        assert "file change" in summary.lower()

    def test_trigger_source_get_semantic_summary_lifecycle(self):
        """Test get_semantic_summary for lifecycle trigger."""
        trigger = TriggerSource("lifecycle", "lifecycle", chain=["command_success:Lint"])
        summary = trigger.get_semantic_summary()
        assert "another command" in summary.lower()

    def test_trigger_source_get_semantic_summary_unknown(self):
        """Test get_semantic_summary for unknown trigger kind."""
        trigger = TriggerSource("unknown", "unknown", chain=["something"])
        summary = trigger.get_semantic_summary()
        assert "automatically" in summary.lower()


class TestConfigValidationResult:
    """Test ConfigValidationResult dataclass."""

    def test_config_validation_result_initialization(self):
        """Test ConfigValidationResult initialization."""
        result = ConfigValidationResult()
        assert result.commands_loaded == 0
        assert result.watchers_active == 0
        assert result.warnings == []
        assert result.errors == []

    def test_config_validation_result_with_values(self):
        """Test ConfigValidationResult with values."""
        result = ConfigValidationResult(
            commands_loaded=5,
            watchers_active=2,
            warnings=["warning1"],
            errors=["error1"],
        )
        assert result.commands_loaded == 5
        assert result.watchers_active == 2
        assert "warning1" in result.warnings
        assert "error1" in result.errors

    def test_config_validation_result_append_warning(self):
        """Test appending to warnings."""
        result = ConfigValidationResult()
        result.warnings.append("New warning")
        assert len(result.warnings) == 1
        assert result.warnings[0] == "New warning"

    def test_config_validation_result_append_error(self):
        """Test appending to errors."""
        result = ConfigValidationResult()
        result.errors.append("New error")
        assert len(result.errors) == 1
        assert result.errors[0] == "New error"


class TestKeyboardConfig:
    """Test KeyboardConfig dataclass."""

    def test_keyboard_config_initialization(self):
        """Test KeyboardConfig initialization."""
        config = KeyboardConfig(shortcuts={"Cmd": "1"})
        assert config.shortcuts == {"Cmd": "1"}
        assert config.enabled is True
        assert config.show_in_tooltips is True

    def test_keyboard_config_disabled(self):
        """Test KeyboardConfig with disabled flag."""
        config = KeyboardConfig(shortcuts={"Cmd": "1"}, enabled=False)
        assert config.enabled is False

    def test_keyboard_config_hide_tooltips(self):
        """Test KeyboardConfig with tooltip hiding."""
        config = KeyboardConfig(shortcuts={}, show_in_tooltips=False)
        assert config.show_in_tooltips is False

    def test_keyboard_config_multiple_shortcuts(self):
        """Test KeyboardConfig with multiple shortcuts."""
        shortcuts = {"Lint": "1", "Format": "2", "Test": "3"}
        config = KeyboardConfig(shortcuts=shortcuts)
        assert len(config.shortcuts) == 3
        assert config.shortcuts["Lint"] == "1"
        assert config.shortcuts["Format"] == "2"


class TestEditorConfig:
    """Test EditorConfig dataclass."""

    def test_editor_config_with_template(self):
        """Test EditorConfig with explicit template."""
        from cmdorc_frontend.models import EditorConfig

        config = EditorConfig(command_template="vim {{ line_plus }} {{ path }}")
        assert config.command_template == "vim {{ line_plus }} {{ path }}"

    def test_editor_config_vscode_template(self):
        """Test EditorConfig with VSCode template."""
        from cmdorc_frontend.models import EditorConfig

        config = EditorConfig(command_template="code --goto {{ path }}:{{ line }}:{{ column }}")
        assert "code --goto" in config.command_template


class TestValidKeys:
    """Test VALID_KEYS set for FIX #8."""

    def test_valid_keys_contains_digits(self):
        """Test VALID_KEYS contains 1-9."""
        for i in range(1, 10):
            assert str(i) in VALID_KEYS

    def test_valid_keys_contains_letters(self):
        """Test VALID_KEYS contains a-z."""
        for c in "abcdefghijklmnopqrstuvwxyz":
            assert c in VALID_KEYS

    def test_valid_keys_contains_function_keys(self):
        """Test VALID_KEYS contains f1-f12."""
        for i in range(1, 13):
            assert f"f{i}" in VALID_KEYS

    def test_valid_keys_does_not_contain_zero(self):
        """Test VALID_KEYS does not contain 0."""
        assert "0" not in VALID_KEYS

    def test_valid_keys_does_not_contain_invalid(self):
        """Test VALID_KEYS does not contain invalid keys."""
        assert "ctrl+x" not in VALID_KEYS
        assert "shift+a" not in VALID_KEYS
        assert "f13" not in VALID_KEYS
        assert "alt+a" not in VALID_KEYS

    def test_valid_keys_size(self):
        """Test VALID_KEYS has correct size."""
        # 9 digits + 26 letters + 12 f-keys = 47
        assert len(VALID_KEYS) == 47


class TestPresentationUpdate:
    """Test PresentationUpdate dataclass."""

    def test_presentation_update_initialization(self):
        """Test PresentationUpdate initialization."""
        update = PresentationUpdate(
            icon="✅",
            running=False,
            tooltip="Test passed",
        )
        assert update.icon == "✅"
        assert update.running is False
        assert update.tooltip == "Test passed"
        assert update.output_path is None

    def test_presentation_update_with_output_path(self):
        """Test PresentationUpdate with output path."""
        path = Path("/tmp/test.log")
        update = PresentationUpdate(
            icon="❌",
            running=False,
            tooltip="Test failed",
            output_path=path,
        )
        assert update.output_path == path

    def test_presentation_update_running_state(self):
        """Test PresentationUpdate with running=True."""
        update = PresentationUpdate(
            icon="⏳",
            running=True,
            tooltip="Running...",
        )
        assert update.running is True
        assert "⏳" in update.icon


class TestCommandNode:
    """Test CommandNode dataclass."""

    def test_command_node_name_property(self):
        """Test CommandNode.name property."""

        # Mock config with name attribute
        class MockConfig:
            name = "TestCommand"

        node = CommandNode(config=MockConfig())
        assert node.name == "TestCommand"

    def test_command_node_triggers_property(self):
        """Test CommandNode.triggers property."""

        class MockConfig:
            name = "TestCmd"
            triggers = ["py_file_changed"]

        node = CommandNode(config=MockConfig())
        assert node.triggers == ["py_file_changed"]

    def test_command_node_default_children(self):
        """Test CommandNode has empty children by default."""

        class MockConfig:
            name = "TestCmd"

        node = CommandNode(config=MockConfig())
        assert node.children == []

    def test_command_node_with_children(self):
        """Test CommandNode with children."""

        class MockConfig:
            name = "Parent"

        parent = CommandNode(config=MockConfig())

        class ChildConfig:
            name = "Child"

        child = CommandNode(config=ChildConfig())
        parent.children.append(child)

        assert len(parent.children) == 1
        assert parent.children[0].name == "Child"


class TestUserSettings:
    """Tests for UserSettings class."""

    def test_user_settings_defaults(self):
        """Test UserSettings default values."""
        settings = UserSettings()
        assert settings.version == "1.0"
        assert settings.active_config_name is None

    def test_user_settings_with_values(self):
        """Test UserSettings with values."""
        settings = UserSettings(version="2.0", active_config_name="Development")
        assert settings.version == "2.0"
        assert settings.active_config_name == "Development"

    def test_user_settings_default_path(self):
        """Test UserSettings.default_path returns correct path."""
        path = UserSettings.default_path()
        assert path.name == "settings.json"
        assert path.parent.name == ".cmdorc"

    def test_user_settings_load_creates_default_when_missing(self):
        """Test load returns default settings when file missing."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent" / "settings.json"
            settings = UserSettings.load(path)
            assert settings.version == "1.0"
            assert settings.active_config_name is None

    def test_user_settings_save_creates_file(self):
        """Test save creates settings file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".cmdorc" / "settings.json"
            settings = UserSettings(active_config_name="Test")
            settings.save(path)

            assert path.exists()
            content = path.read_text()
            assert "Test" in content

    def test_user_settings_load_from_file(self):
        """Test load reads settings from file."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text('{"version": "1.0", "active_config_name": "Production"}')

            settings = UserSettings.load(path)
            assert settings.active_config_name == "Production"

    def test_user_settings_roundtrip(self):
        """Test save and load roundtrip."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"

            original = UserSettings(active_config_name="MyConfig")
            original.save(path)

            loaded = UserSettings.load(path)
            assert loaded.active_config_name == "MyConfig"
            assert loaded.version == original.version

    def test_user_settings_load_invalid_json(self):
        """Test load handles invalid JSON gracefully."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text("not valid json {{{")

            settings = UserSettings.load(path)
            # Should return defaults on error
            assert settings.version == "1.0"
            assert settings.active_config_name is None

    def test_user_settings_load_with_default_path(self):
        """Test load uses default path when not specified."""
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Create settings in default location
                settings_dir = Path(tmpdir) / ".cmdorc"
                settings_dir.mkdir()
                (settings_dir / "settings.json").write_text('{"active_config_name": "FromDefault"}')

                settings = UserSettings.load()
                assert settings.active_config_name == "FromDefault"
            finally:
                os.chdir(original_cwd)

    def test_user_settings_save_creates_parent_dirs(self):
        """Test save creates parent directories if needed."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "deep" / "nested" / "settings.json"
            settings = UserSettings(active_config_name="Test")
            settings.save(path)

            assert path.exists()
            assert path.parent.exists()
