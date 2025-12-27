"""CLI entry point for cmdorc-tui: auto-generates default config and launches the TUI."""

import argparse
import logging
import sys
from pathlib import Path

from textual_cmdorc import __version__
from textual_cmdorc.simple_app import SimpleApp

logging.getLogger("textual_cmdorc").setLevel(logging.DEBUG)

# Default config template for Python development workflows
DEFAULT_CONFIG_TEMPLATE = """\
# Auto-generated config.toml for cmdorc-tui

[variables]
base_dir = "."

[[file_watcher]]
dir = "."
patterns = ["**/*.py"]
trigger = "py_file_changed"
debounce_ms = 300
ignore_dirs = ["__pycache__", ".git", "venv", ".venv"]

[[command]]
name = "Lint"
command = "ruff check --fix ."
triggers = ["py_file_changed"]
max_concurrent = 1

[[command]]
name = "Format"
command = "ruff format ."
triggers = ["command_success:Lint"]
max_concurrent = 1

[[command]]
name = "Tests"
command = "pytest {{ base_dir }}"
triggers = ["command_success:Format"]

[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3" }
enabled = true
show_in_tooltips = true
"""


def create_default_config(config_path: Path) -> bool:
    """
    Create a default config.toml if it doesn't exist.

    Args:
        config_path: Path where config should be created

    Returns:
        True if config was created, False if it already exists

    Raises:
        PermissionError: If unable to write to the directory
        OSError: If other file system errors occur
    """
    if config_path.exists():
        return False

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write template to config file
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
    return True


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        prog="cmdorc-tui",
        description="A TUI frontend for cmdorc command orchestration.",
        epilog="Examples:\n"
        "  cmdorc-tui                      # Auto-create config.toml and launch\n"
        "  cmdorc-tui --config my-flow.toml # Use custom config\n"
        "  cmdorc-tui --version             # Show version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config",
        default="config.toml",
        help="Path to config file (default: config.toml)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args()


def main() -> None:
    """
    Main entry point for cmdorc-tui CLI.

    Handles:
    - Argument parsing
    - Auto-creation of config.toml
    - Launching CmdorcApp
    - Error handling and exit codes
    """
    args = parse_args()

    # Resolve config path to absolute path
    config_path = Path(args.config).resolve()

    try:
        # Try to create default config if missing
        if create_default_config(config_path):
            print(f"Created default config at: {config_path}")

        # Validate config exists (should be guaranteed by create_default_config)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)

        # Launch the app
        app = SimpleApp(config_path=str(config_path))
        app.run()

    except KeyboardInterrupt:
        # Gracefully handle Ctrl+C
        sys.exit(130)
    except (PermissionError, OSError) as e:
        print(f"Error: Failed to create config: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
