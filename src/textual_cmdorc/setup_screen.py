"""Setup screen for first-run experience when no config found."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label

from cmdorc_frontend.config_discovery import (
    MULTI_CONFIG_FILENAME,
    find_toml_files,
    generate_cmdorc_tui_toml,
)


class SetupScreen(ModalScreen[str | None]):
    """Initial setup screen when no configuration found.

    Shows options:
    1. Create commands.toml (simple single-file setup)
    2. Create cmdorc-tui.toml (multi-config from existing files)
    3. Exit

    Returns:
        String indicating action taken or None if cancelled
    """

    CSS = """
    SetupScreen {
        align: center middle;
    }

    SetupScreen > Vertical {
        width: 60;
        height: auto;
        max-height: 20;
        padding: 1 2;
        border: solid $accent;
        background: $surface;
    }

    SetupScreen .title {
        text-align: center;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    SetupScreen .message {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    SetupScreen Button {
        width: 100%;
        margin: 0 0 1 0;
    }

    SetupScreen #btn-exit {
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("1", "create_single", "Create commands.toml", show=False),
        Binding("2", "create_multi", "Create cmdorc-tui.toml", show=False),
        Binding("3", "quit", "Exit", show=False),
        Binding("escape", "quit", "Exit", show=False),
    ]

    DEFAULT_COMMANDS_TEMPLATE = """\
# cmdorc-tui configuration file
# Documentation: https://github.com/eyecantell/cmdorc

[variables]
base_dir = "."

[[command]]
name = "Example"
command = "echo 'Hello from cmdorc-tui!'"
triggers = ["say_hello"]

# More examples below:
#
# [[file_watcher]]
# dir = "."
# extensions = [".py"]
# recursive = true
# trigger_emitted = "py_file_changed"
# debounce_ms = 300
# ignore_dirs = ["__pycache__", ".git", "venv", ".venv"]
#
# [[command]]
# name = "Lint"
# command = "ruff check --fix ."
# triggers = ["py_file_changed"]
# max_concurrent = 1
#
# [[command]]
# name = "Format"
# command = "ruff format ."
# triggers = ["command_success:Lint"]
# max_concurrent = 1
#
# [[command]]
# name = "Tests"
# command = "pytest {{ base_dir }}"
# triggers = ["command_success:Format"]
# max_concurrent = 1
#
# [output_storage]
# directory = ".cmdorc/outputs"
# keep_history = 10
#
# [editor]
# command_template = "code --goto {{ path }}:{{ line }}:{{ column }}"  # VSCode (default)
# # Other options:
# # command_template = "vim {{ line_plus }} {{ path }}"  # Vim
# # command_template = "subl {{ path }}:{{ line }}:{{ column }}"  # Sublime Text
#
# [keyboard]
# shortcuts = { Lint = "1", Format = "2", Tests = "3" }
# enabled = true
# show_in_tooltips = true
"""

    def compose(self) -> ComposeResult:
        """Compose the setup screen UI."""
        toml_files = find_toml_files()
        has_existing = len(toml_files) > 0

        with Vertical():
            yield Label("Welcome to cmdorc-tui!", classes="title")
            yield Label("No configuration found.", classes="message")

            yield Button(
                "[1] Create commands.toml (simple setup)",
                id="btn-single",
                variant="default",
            )

            multi_label = "[2] Create cmdorc-tui.toml"
            if has_existing:
                multi_label += f" (from {len(toml_files)} existing .toml)"
            else:
                multi_label += " (multi-config)"
            yield Button(multi_label, id="btn-multi", variant="default")

            yield Button("[3] Exit", id="btn-exit", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-single":
            self.action_create_single()
        elif event.button.id == "btn-multi":
            self.action_create_multi()
        elif event.button.id == "btn-exit":
            self.action_quit()

    def action_create_single(self) -> None:
        """Create commands.toml and dismiss."""
        cwd = Path.cwd()
        config_path = cwd / "commands.toml"

        if config_path.exists():
            self.dismiss("commands.toml already exists")
            return

        config_path.write_text(self.DEFAULT_COMMANDS_TEMPLATE)
        self.dismiss(f"Created {config_path}")

    def action_create_multi(self) -> None:
        """Create cmdorc-tui.toml and dismiss."""
        cwd = Path.cwd()
        meta_path = cwd / MULTI_CONFIG_FILENAME

        if meta_path.exists():
            self.dismiss(f"{MULTI_CONFIG_FILENAME} already exists")
            return

        toml_files = find_toml_files()

        if toml_files:
            # Generate from existing files
            content = generate_cmdorc_tui_toml(toml_files, cwd)
        else:
            # Create template with placeholder
            content = """\
# cmdorc-tui multi-config file
# First config is the default

[[config]]
name = "Default"
files = ["./commands.toml"]

# Add more configs:
# [[config]]
# name = "Development"
# files = ["./dev.toml", "./test.toml"]
"""
            # Also create commands.toml if it doesn't exist
            commands_path = cwd / "commands.toml"
            if not commands_path.exists():
                commands_path.write_text(self.DEFAULT_COMMANDS_TEMPLATE)

        meta_path.write_text(content)
        self.dismiss(f"Created {meta_path}")

    def action_quit(self) -> None:
        """Exit without creating config."""
        self.dismiss(None)
