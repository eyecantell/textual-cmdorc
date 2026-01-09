"""Tests for SetupScreen."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from cmdorc_frontend.config_discovery import MULTI_CONFIG_FILENAME
from textual_cmdorc.setup_screen import SetupScreen


class TestSetupScreenActions:
    """Tests for SetupScreen action methods."""

    def test_create_single_creates_commands_toml(self):
        """action_create_single creates commands.toml."""
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                screen = SetupScreen()
                screen._dismiss_result = None

                def capture_dismiss(result):
                    screen._dismiss_result = result

                screen.dismiss = capture_dismiss

                screen.action_create_single()

                assert (Path(tmpdir) / "commands.toml").exists()
                assert "Created" in screen._dismiss_result
            finally:
                os.chdir(original_cwd)

    def test_create_single_no_overwrite(self):
        """action_create_single doesn't overwrite existing file."""
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                existing = Path(tmpdir) / "commands.toml"
                existing.write_text("# existing\n")

                screen = SetupScreen()
                screen._dismiss_result = None
                screen.dismiss = lambda result: setattr(screen, "_dismiss_result", result)

                screen.action_create_single()

                assert existing.read_text() == "# existing\n"
                assert "already exists" in screen._dismiss_result
            finally:
                os.chdir(original_cwd)

    def test_create_multi_from_existing_files(self):
        """action_create_multi generates from existing TOML files."""
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                (Path(tmpdir) / "build.toml").write_text("[[command]]\nname = 'Build'\ncommand = 'echo build'\n")
                (Path(tmpdir) / "test.toml").write_text("[[command]]\nname = 'Test'\ncommand = 'echo test'\n")

                screen = SetupScreen()
                screen._dismiss_result = None
                screen.dismiss = lambda result: setattr(screen, "_dismiss_result", result)

                screen.action_create_multi()

                meta_path = Path(tmpdir) / MULTI_CONFIG_FILENAME
                assert meta_path.exists()
                content = meta_path.read_text()
                assert "build.toml" in content
                assert "test.toml" in content
                assert "Created" in screen._dismiss_result
            finally:
                os.chdir(original_cwd)

    def test_create_multi_creates_template_when_no_existing(self):
        """action_create_multi creates template when no existing TOML files."""
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                screen = SetupScreen()
                screen._dismiss_result = None
                screen.dismiss = lambda result: setattr(screen, "_dismiss_result", result)

                screen.action_create_multi()

                meta_path = Path(tmpdir) / MULTI_CONFIG_FILENAME
                assert meta_path.exists()
                # Should also create commands.toml
                assert (Path(tmpdir) / "commands.toml").exists()
                assert "Created" in screen._dismiss_result
            finally:
                os.chdir(original_cwd)

    def test_create_multi_no_overwrite(self):
        """action_create_multi doesn't overwrite existing file."""
        with TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                existing = Path(tmpdir) / MULTI_CONFIG_FILENAME
                existing.write_text("# existing\n")

                screen = SetupScreen()
                screen._dismiss_result = None
                screen.dismiss = lambda result: setattr(screen, "_dismiss_result", result)

                screen.action_create_multi()

                assert existing.read_text() == "# existing\n"
                assert "already exists" in screen._dismiss_result
            finally:
                os.chdir(original_cwd)

    def test_action_quit_dismisses_none(self):
        """action_quit dismisses with None."""
        screen = SetupScreen()
        screen._dismiss_result = "not-none"
        screen.dismiss = lambda result: setattr(screen, "_dismiss_result", result)

        screen.action_quit()

        assert screen._dismiss_result is None


class TestSetupScreenTemplate:
    """Tests for SetupScreen templates."""

    def test_commands_template_is_valid(self):
        """DEFAULT_COMMANDS_TEMPLATE is valid TOML."""
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib

        screen = SetupScreen()
        # Should not raise
        data = tomllib.loads(screen.DEFAULT_COMMANDS_TEMPLATE)
        assert "variables" in data
        assert "command" in data

    def test_commands_template_has_example(self):
        """DEFAULT_COMMANDS_TEMPLATE has example command."""
        screen = SetupScreen()
        assert "Example" in screen.DEFAULT_COMMANDS_TEMPLATE
        assert 'command = "echo' in screen.DEFAULT_COMMANDS_TEMPLATE


class TestSetupScreenBindings:
    """Tests for SetupScreen key bindings."""

    def test_bindings_defined(self):
        """SetupScreen has expected key bindings."""
        bindings = {b.key: b.action for b in SetupScreen.BINDINGS}
        assert "1" in bindings
        assert "2" in bindings
        assert "3" in bindings
        assert "escape" in bindings
