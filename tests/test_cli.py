"""Tests for textual_cmdorc.cli module."""

import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from cmdorc_frontend.config import load_frontend_config
from textual_cmdorc.cli import (
    DEFAULT_CONFIG_TEMPLATE,
    create_default_config,
    main,
    parse_args,
)


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_create_default_config_success(self):
        """Test successful config creation."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            result = create_default_config(config_path)

            assert result is True
            assert config_path.exists()
            assert config_path.read_text() == DEFAULT_CONFIG_TEMPLATE

    def test_create_default_config_already_exists(self):
        """Test that existing config is not overwritten."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            existing_content = "# Existing config"
            config_path.write_text(existing_content)

            result = create_default_config(config_path)

            assert result is False
            assert config_path.read_text() == existing_content

    def test_create_default_config_creates_parent_dirs(self):
        """Test that parent directories are created."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "nested" / "config.toml"
            result = create_default_config(config_path)

            assert result is True
            assert config_path.exists()
            assert config_path.parent.exists()

    def test_create_default_config_permission_error(self):
        """Test handling of permission errors."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Mock Path.write_text to raise PermissionError
            with patch.object(Path, "write_text", side_effect=PermissionError("Access denied")):
                with pytest.raises(PermissionError):
                    create_default_config(config_path)

    def test_create_default_config_template_valid_toml(self):
        """Test that the default template is valid TOML."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            # Should not raise an exception
            runner_config, keyboard_config, watchers, _ = load_frontend_config(config_path)

            assert runner_config is not None
            assert keyboard_config is not None
            assert watchers is not None


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_args_default(self):
        """Test default arguments."""
        with patch.object(sys, "argv", ["cmdorc-tui"]):
            args = parse_args()
            assert args.config == "config.toml"

    def test_parse_args_custom_config_short_flag(self):
        """Test custom config with -c flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "-c", "custom.toml"]):
            args = parse_args()
            assert args.config == "custom.toml"

    def test_parse_args_custom_config_long_flag(self):
        """Test custom config with --config flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--config", "custom.toml"]):
            args = parse_args()
            assert args.config == "custom.toml"

    def test_parse_args_version_flag(self):
        """Test --version flag exits with version."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args()
            assert exc_info.value.code == 0

    def test_parse_args_help_flag(self):
        """Test --help flag exits with help."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                parse_args()
            assert exc_info.value.code == 0


class TestMain:
    """Tests for main function."""

    def test_main_with_existing_config(self):
        """Test main function with existing config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            with patch.object(sys, "argv", ["cmdorc-tui", "-c", str(config_path)]):
                with patch("textual_cmdorc.cli.CmdorcApp") as mock_app:
                    mock_instance = MagicMock()
                    mock_app.return_value = mock_instance

                    main()

                    # Verify CmdorcApp was called with the config path
                    mock_app.assert_called_once_with(config_path=str(config_path))
                    mock_instance.run.assert_called_once()

    def test_main_auto_creates_config(self):
        """Test that main auto-creates missing config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            with patch.object(sys, "argv", ["cmdorc-tui", "-c", str(config_path)]):
                with patch("textual_cmdorc.cli.CmdorcApp") as mock_app:
                    mock_instance = MagicMock()
                    mock_app.return_value = mock_instance
                    with patch("builtins.print") as mock_print:
                        main()

                    # Verify config was created
                    assert config_path.exists()

                    # Verify creation message was printed
                    mock_print.assert_called_once()
                    call_args = mock_print.call_args[0][0]
                    assert "Created default config at:" in call_args
                    assert str(config_path) in call_args

    def test_main_keyboard_interrupt(self):
        """Test handling of KeyboardInterrupt (Ctrl+C)."""
        with patch.object(sys, "argv", ["cmdorc-tui"]), patch("textual_cmdorc.cli.CmdorcApp") as mock_app:
            mock_instance = MagicMock()
            mock_instance.run.side_effect = KeyboardInterrupt()
            mock_app.return_value = mock_instance

            with pytest.raises(SystemExit) as exc_info:
                main()

            # Exit code 130 for Ctrl+C
            assert exc_info.value.code == 130

    def test_main_permission_error(self):
        """Test handling of permission errors."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            with (
                patch.object(sys, "argv", ["cmdorc-tui", "-c", str(config_path)]),
                patch("textual_cmdorc.cli.create_default_config", side_effect=PermissionError("Access denied")),
                patch("sys.stderr", new_callable=StringIO),
                pytest.raises(SystemExit) as exc_info
            ):
                main()

            assert exc_info.value.code == 1

    def test_main_runtime_error(self):
        """Test handling of runtime errors."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            with (patch.object(sys, "argv", ["cmdorc-tui", "-c", str(config_path)]),
                   patch("textual_cmdorc.cli.CmdorcApp") as mock_app
            ):
                mock_instance = MagicMock()
                mock_instance.run.side_effect = RuntimeError("App error")
                mock_app.return_value = mock_instance

                with (patch("sys.stderr", new_callable=StringIO),
                    pytest.raises(SystemExit) as exc_info):
                    main()

                assert exc_info.value.code == 1

    def test_main_resolves_config_path_to_absolute(self):
        """Test that config path is resolved to absolute path."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            # Use relative path
            with (patch.object(sys, "argv", ["cmdorc-tui", "-c", "config.toml"]),
                  patch("textual_cmdorc.cli.CmdorcApp") as mock_app):
                mock_instance = MagicMock()
                mock_app.return_value = mock_instance

                # Change to temp directory
                import os

                original_cwd = os.getcwd()
                try:
                    os.chdir(tmpdir)
                    main()

                    # Verify that the path passed to CmdorcApp is absolute
                    call_args = mock_app.call_args
                    passed_path = call_args[1]["config_path"]
                    assert Path(passed_path).is_absolute()
                finally:
                    os.chdir(original_cwd)


class TestDefaultConfigTemplate:
    """Tests for the default config template."""

    def test_template_is_valid_toml(self):
        """Test that the template is valid TOML."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(DEFAULT_CONFIG_TEMPLATE)

            # Should not raise an exception
            runner_config, keyboard_config, watchers, _ = load_frontend_config(config_path)
            assert runner_config is not None

    def test_template_has_variables_section(self):
        """Test that template has [variables] section."""
        assert "[variables]" in DEFAULT_CONFIG_TEMPLATE
        assert 'base_dir = "."' in DEFAULT_CONFIG_TEMPLATE

    def test_template_has_file_watcher_section(self):
        """Test that template has [[file_watcher]] section."""
        assert "[[file_watcher]]" in DEFAULT_CONFIG_TEMPLATE
        assert 'dir = "."' in DEFAULT_CONFIG_TEMPLATE
        assert 'patterns = ["**/*.py"]' in DEFAULT_CONFIG_TEMPLATE
        assert 'trigger = "py_file_changed"' in DEFAULT_CONFIG_TEMPLATE

    def test_template_has_command_sections(self):
        """Test that template has [[command]] sections."""
        assert "[[command]]" in DEFAULT_CONFIG_TEMPLATE
        assert 'name = "Lint"' in DEFAULT_CONFIG_TEMPLATE
        assert 'name = "Format"' in DEFAULT_CONFIG_TEMPLATE
        assert 'name = "Tests"' in DEFAULT_CONFIG_TEMPLATE

    def test_template_has_keyboard_section(self):
        """Test that template has [keyboard] section."""
        assert "[keyboard]" in DEFAULT_CONFIG_TEMPLATE
        assert 'shortcuts = { Lint = "1", Format = "2", Tests = "3" }' in DEFAULT_CONFIG_TEMPLATE
        assert "enabled = true" in DEFAULT_CONFIG_TEMPLATE
        assert "show_in_tooltips = true" in DEFAULT_CONFIG_TEMPLATE

    def test_template_has_trigger_chain(self):
        """Test that template has proper trigger chain."""
        assert 'triggers = ["py_file_changed"]' in DEFAULT_CONFIG_TEMPLATE
        assert 'triggers = ["command_success:Lint"]' in DEFAULT_CONFIG_TEMPLATE
        assert 'triggers = ["command_success:Format"]' in DEFAULT_CONFIG_TEMPLATE

    def test_template_loads_with_load_frontend_config(self):
        """Test that template loads successfully with load_frontend_config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(DEFAULT_CONFIG_TEMPLATE)

            runner_config, keyboard_config, watchers, command_nodes = load_frontend_config(config_path)

            # Verify structure
            assert runner_config is not None
            assert keyboard_config is not None
            assert len(watchers) > 0
            assert len(command_nodes) > 0

            # Verify keyboard config
            assert keyboard_config.enabled is True
            assert keyboard_config.show_in_tooltips is True
            assert "Lint" in keyboard_config.shortcuts
            assert keyboard_config.shortcuts["Lint"] == "1"

            # Verify watcher config
            assert watchers[0].trigger == "py_file_changed"
            assert "**/*.py" in (watchers[0].patterns or [])


class TestActionCommand:
    """Tests for CmdorcApp.action_command() method."""

    def test_action_command_calls_controller_request_run(self):
        """Test that action_command() calls controller.request_run()."""
        from textual_cmdorc.app import CmdorcApp

        app = CmdorcApp(config_path="config.toml")

        # Mock controller
        mock_controller = MagicMock()
        app.controller = mock_controller

        # Call action with command name
        app.action_command("Lint")

        # Verify controller.request_run was called with correct command name
        mock_controller.request_run.assert_called_once_with("Lint")

    def test_action_command_handles_no_controller(self):
        """Test that action_command() gracefully handles missing controller."""
        from textual_cmdorc.app import CmdorcApp

        app = CmdorcApp(config_path="config.toml")
        app.controller = None

        # Should not raise exception, just log warning
        app.action_command("Lint")

    def test_action_command_with_multiple_command_names(self):
        """Test action_command() with various command names."""
        from textual_cmdorc.app import CmdorcApp

        app = CmdorcApp(config_path="config.toml")
        mock_controller = MagicMock()
        app.controller = mock_controller

        # Test multiple command names
        command_names = ["Lint", "Format", "Tests", "Build"]
        for cmd_name in command_names:
            app.action_command(cmd_name)

        # Verify each was called
        assert mock_controller.request_run.call_count == len(command_names)
        calls = [call[0][0] for call in mock_controller.request_run.call_args_list]
        assert calls == command_names

    def test_action_command_uses_sync_safe_request_run(self):
        """Test that action_command() uses request_run (not async run_command)."""
        from textual_cmdorc.app import CmdorcApp

        app = CmdorcApp(config_path="config.toml")
        mock_controller = MagicMock()
        app.controller = mock_controller

        # Call action
        app.action_command("Lint")

        # Verify request_run was called (not run_command)
        mock_controller.request_run.assert_called_once_with("Lint")
        mock_controller.run_command.assert_not_called()
