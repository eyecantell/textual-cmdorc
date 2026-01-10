"""Tests for textual_cmdorc.cli module."""

import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from cmdorc_frontend.config import load_frontend_config
from cmdorc_frontend.config_discovery import MULTI_CONFIG_FILENAME
from textual_cmdorc.cli import (
    DEFAULT_CONFIG_TEMPLATE,
    create_default_config,
    handle_init_configs,
    handle_list_configs,
    handle_validate,
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
            with (
                patch.object(Path, "write_text", side_effect=PermissionError("Access denied")),
                pytest.raises(PermissionError),
            ):
                create_default_config(config_path)

    def test_create_default_config_template_valid_toml(self):
        """Test that the default template is valid TOML."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            # Should not raise an exception
            runner_config, keyboard_config, watchers, _, _ = load_frontend_config(config_path)

            assert runner_config is not None
            assert keyboard_config is not None
            assert watchers is not None


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_args_default(self):
        """Test default arguments."""
        with patch.object(sys, "argv", ["cmdorc-tui"]):
            args = parse_args()
            # config is None by default, uses config discovery
            assert args.config is None

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

    def test_parse_args_verbose_flag(self):
        """Test --verbose flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--verbose"]):
            args = parse_args()
            assert args.verbose is True

    def test_parse_args_verbose_short_flag(self):
        """Test -v flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "-v"]):
            args = parse_args()
            assert args.verbose is True

    def test_parse_args_no_verbose_flag(self):
        """Test default (no verbose flag)."""
        with patch.object(sys, "argv", ["cmdorc-tui"]):
            args = parse_args()
            assert args.verbose is False

    def test_parse_args_log_file_flag(self):
        """Test --log-file flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--log-file"]):
            args = parse_args()
            assert args.log_file is True

    def test_parse_args_no_log_file_flag(self):
        """Test default (no --log-file flag)."""
        with patch.object(sys, "argv", ["cmdorc-tui"]):
            args = parse_args()
            assert args.log_file is False

    def test_parse_args_log_level_flag(self):
        """Test --log-level flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--log-level", "WARNING"]):
            args = parse_args()
            assert args.log_level == "WARNING"

    def test_parse_args_log_level_default(self):
        """Test --log-level default value."""
        with patch.object(sys, "argv", ["cmdorc-tui"]):
            args = parse_args()
            assert args.log_level == "DEBUG"

    def test_parse_args_log_all_flag(self):
        """Test --log-all flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--log-all"]):
            args = parse_args()
            assert args.log_all is True

    def test_parse_args_no_log_all_flag(self):
        """Test default (no --log-all flag)."""
        with patch.object(sys, "argv", ["cmdorc-tui"]):
            args = parse_args()
            assert args.log_all is False

    def test_parse_args_combined_logging_flags(self):
        """Test combining logging flags."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--log-file", "--log-level", "INFO", "--log-all"]):
            args = parse_args()
            assert args.log_file is True
            assert args.log_level == "INFO"
            assert args.log_all is True

    def test_parse_args_verbose_backward_compat(self):
        """Test that -v is backward compatible (alias for --log-file)."""
        with patch.object(sys, "argv", ["cmdorc-tui", "-v"]):
            args = parse_args()
            assert args.verbose is True

    def test_parse_args_list_configs_flag(self):
        """Test --list-configs flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--list-configs"]):
            args = parse_args()
            assert args.list_configs is True

    def test_parse_args_validate_flag(self):
        """Test --validate flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--validate"]):
            args = parse_args()
            assert args.validate is True

    def test_parse_args_init_configs_flag(self):
        """Test --init-configs flag."""
        with patch.object(sys, "argv", ["cmdorc-tui", "--init-configs"]):
            args = parse_args()
            assert args.init_configs is True


class TestMain:
    """Tests for main function."""

    def test_main_with_existing_config(self):
        """Test main function with existing config."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            with (
                patch.object(sys, "argv", ["cmdorc-tui", "-c", str(config_path)]),
                patch("textual_cmdorc.cli.CmdorcApp") as mock_app,
            ):
                mock_instance = MagicMock()
                mock_app.return_value = mock_instance

                main()

                # Verify CmdorcApp was called with the config path
                mock_app.assert_called_once_with(config_path=str(config_path))
                mock_instance.run.assert_called_once()

    def test_main_shows_setup_screen_when_no_config(self):
        """Test that main launches with show_setup=True when no config found."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                with (
                    patch.object(sys, "argv", ["cmdorc-tui"]),
                    patch("textual_cmdorc.cli.CmdorcApp") as mock_app,
                ):
                    mock_instance = MagicMock()
                    mock_app.return_value = mock_instance
                    main()

                    # Verify CmdorcApp was called with show_setup=True
                    mock_app.assert_called_once_with(show_setup=True)
                    # Verify app.run() was called
                    mock_instance.run.assert_called_once()
            finally:
                os.chdir(original_cwd)

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
                pytest.raises(SystemExit) as exc_info,
            ):
                main()

            assert exc_info.value.code == 1

    def test_main_runtime_error(self):
        """Test handling of runtime errors."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            with (
                patch.object(sys, "argv", ["cmdorc-tui", "-c", str(config_path)]),
                patch("textual_cmdorc.cli.CmdorcApp") as mock_app,
            ):
                mock_instance = MagicMock()
                mock_instance.run.side_effect = RuntimeError("App error")
                mock_app.return_value = mock_instance

                with patch("sys.stderr", new_callable=StringIO), pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_main_resolves_config_path_to_absolute(self):
        """Test that config path is resolved to absolute path."""
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config(config_path)

            # Use relative path
            with (
                patch.object(sys, "argv", ["cmdorc-tui", "-c", "config.toml"]),
                patch("textual_cmdorc.cli.CmdorcApp") as mock_app,
            ):
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


class TestHandleListConfigs:
    """Tests for handle_list_configs function."""

    def test_list_configs_multi_config(self):
        """Test listing configs from cmdorc-tui.toml."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Create cmdorc-tui.toml with multiple configs
                (Path(tmpdir) / "dev.toml").write_text('[[command]]\nname = "Dev"\ncommand = "echo dev"\n')
                (Path(tmpdir) / "prod.toml").write_text('[[command]]\nname = "Prod"\ncommand = "echo prod"\n')
                (Path(tmpdir) / MULTI_CONFIG_FILENAME).write_text(
                    '[[config]]\nname = "Development"\nfiles = ["./dev.toml"]\n\n'
                    '[[config]]\nname = "Production"\nfiles = ["./prod.toml"]\n'
                )

                with patch("builtins.print") as mock_print:
                    result = handle_list_configs()

                assert result == 0
                # Check output contains config names
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "Development" in output
                assert "Production" in output
                assert "[default]" in output
            finally:
                os.chdir(original_cwd)

    def test_list_configs_single_config(self):
        """Test listing single config mode."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                (Path(tmpdir) / "commands.toml").write_text('[[command]]\nname = "Test"\ncommand = "echo test"\n')

                with patch("builtins.print") as mock_print:
                    result = handle_list_configs()

                assert result == 0
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "Single config mode" in output
            finally:
                os.chdir(original_cwd)

    def test_list_configs_no_config(self):
        """Test listing when no config found."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                with patch("builtins.print") as mock_print:
                    result = handle_list_configs()

                assert result == 1
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "No configuration found" in output
            finally:
                os.chdir(original_cwd)


class TestHandleValidate:
    """Tests for handle_validate function."""

    def test_validate_valid_config(self):
        """Test validating a valid cmdorc-tui.toml."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                (Path(tmpdir) / "dev.toml").write_text('[[command]]\nname = "Dev"\ncommand = "echo dev"\n')
                (Path(tmpdir) / MULTI_CONFIG_FILENAME).write_text(
                    '[[config]]\nname = "Development"\nfiles = ["./dev.toml"]\n'
                )

                with patch("builtins.print") as mock_print:
                    result = handle_validate()

                assert result == 0
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "is valid" in output
            finally:
                os.chdir(original_cwd)

    def test_validate_missing_file(self):
        """Test validating with missing referenced file."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                (Path(tmpdir) / MULTI_CONFIG_FILENAME).write_text(
                    '[[config]]\nname = "Development"\nfiles = ["./missing.toml"]\n'
                )

                with patch("builtins.print") as mock_print:
                    result = handle_validate()

                assert result == 1
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "Missing" in output
            finally:
                os.chdir(original_cwd)

    def test_validate_no_multi_config(self):
        """Test validating when no cmdorc-tui.toml exists."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                with patch("builtins.print") as mock_print:
                    result = handle_validate()

                assert result == 1
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "No" in output and "found" in output
            finally:
                os.chdir(original_cwd)


class TestHandleInitConfigs:
    """Tests for handle_init_configs function."""

    def test_init_configs_creates_file(self):
        """Test that init-configs creates cmdorc-tui.toml."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                (Path(tmpdir) / "build.toml").write_text("[[command]]\nname = 'Build'\ncommand = 'echo build'\n")
                (Path(tmpdir) / "test.toml").write_text("[[command]]\nname = 'Test'\ncommand = 'echo test'\n")

                with patch("builtins.print"):
                    result = handle_init_configs()

                assert result == 0
                assert (Path(tmpdir) / MULTI_CONFIG_FILENAME).exists()
                content = (Path(tmpdir) / MULTI_CONFIG_FILENAME).read_text()
                assert "build.toml" in content
                assert "test.toml" in content
            finally:
                os.chdir(original_cwd)

    def test_init_configs_refuses_overwrite(self):
        """Test that init-configs doesn't overwrite existing file."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                (Path(tmpdir) / MULTI_CONFIG_FILENAME).write_text("# existing\n")

                with patch("builtins.print") as mock_print:
                    result = handle_init_configs()

                assert result == 1
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "already exists" in output
            finally:
                os.chdir(original_cwd)

    def test_init_configs_no_toml_files(self):
        """Test init-configs when no TOML files found."""
        with TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                with patch("builtins.print") as mock_print:
                    result = handle_init_configs()

                assert result == 1
                output = " ".join(str(call) for call in mock_print.call_args_list)
                assert "No TOML files found" in output
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
            runner_config, keyboard_config, watchers, _, _ = load_frontend_config(config_path)
            assert runner_config is not None

    def test_template_has_variables_section(self):
        """Test that template has [variables] section."""
        assert "[variables]" in DEFAULT_CONFIG_TEMPLATE
        assert 'base_dir = "."' in DEFAULT_CONFIG_TEMPLATE

    def test_template_has_file_watcher_section(self):
        """Test that template has [[file_watcher]] section."""
        assert "[[file_watcher]]" in DEFAULT_CONFIG_TEMPLATE
        assert 'dir = "."' in DEFAULT_CONFIG_TEMPLATE
        assert 'extensions = [".py"]' in DEFAULT_CONFIG_TEMPLATE
        assert "recursive = true" in DEFAULT_CONFIG_TEMPLATE
        assert 'trigger_emitted = "py_file_changed"' in DEFAULT_CONFIG_TEMPLATE

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

    def test_template_has_output_storage_section(self):
        """Test that template has [output_storage] section for persisting command outputs.

        This is critical - without output_storage, cmdorc defaults to keep_history=0
        which means no output files are created, breaking output linking in the UI.
        """
        assert "[output_storage]" in DEFAULT_CONFIG_TEMPLATE
        assert 'directory = ".cmdorc/outputs"' in DEFAULT_CONFIG_TEMPLATE
        assert "keep_history = " in DEFAULT_CONFIG_TEMPLATE
        # Ensure keep_history is > 0 (any positive number works)
        import re

        match = re.search(r"keep_history\s*=\s*(\d+)", DEFAULT_CONFIG_TEMPLATE)
        assert match is not None, "keep_history not found in template"
        assert int(match.group(1)) >= 1, "keep_history must be >= 1 to persist outputs"

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

            runner_config, keyboard_config, watchers, command_nodes, _ = load_frontend_config(config_path)

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
            assert watchers[0].trigger_emitted == "py_file_changed"
            assert ".py" in (watchers[0].extensions or [])
            assert watchers[0].recursive is True

            # Verify output_storage config (prevents regression where outputs aren't persisted)
            assert runner_config.output_storage is not None
            assert runner_config.output_storage.keep_history >= 1, "keep_history must be >= 1 to persist outputs"
