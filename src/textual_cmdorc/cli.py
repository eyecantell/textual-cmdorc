"""CLI entry point for cmdorc-tui: auto-generates default config and launches the TUI."""

import argparse
import sys
from pathlib import Path

from cmdorc_frontend.config_discovery import (
    MULTI_CONFIG_FILENAME,
    discover_config,
    find_toml_files,
    generate_cmdorc_tui_toml,
    resolve_startup_config,
)
from textual_cmdorc import __version__
from textual_cmdorc.cmdorc_app import CmdorcApp

# Default config template for Python development workflows
DEFAULT_CONFIG_TEMPLATE = """\
# Auto-generated config.toml for cmdorc-tui

[variables]
base_dir = "."

[[file_watcher]]
dir = "."
extensions = [".py"]
recursive = true
trigger_emitted = "py_file_changed"
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

[output_storage]
directory = ".cmdorc/outputs"
keep_history = 10

[editor]
command_template = "code --goto {{ path }}:{{ line }}:{{ column }}"

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
        "  cmdorc-tui                         # Auto-detect config and launch\n"
        "  cmdorc-tui --config my-flow.toml   # Use specific config file\n"
        "  cmdorc-tui --config Development    # Use named config from cmdorc-tui.toml\n"
        "  cmdorc-tui --list-configs          # List available named configs\n"
        "  cmdorc-tui --validate              # Validate cmdorc-tui.toml\n"
        "  cmdorc-tui --init-configs          # Generate cmdorc-tui.toml from TOML files\n"
        "  cmdorc-tui --log-file              # Enable logging to .cmdorc/logs/cmdorc-tui.log\n"
        "  cmdorc-tui --version               # Show version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Config file path OR named config from cmdorc-tui.toml",
    )

    parser.add_argument(
        "--list-configs",
        action="store_true",
        help="List available named configs from cmdorc-tui.toml",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate cmdorc-tui.toml and check all referenced files exist",
    )

    parser.add_argument(
        "--init-configs",
        action="store_true",
        help="Auto-generate cmdorc-tui.toml from found TOML files",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--log-file",
        action="store_true",
        help="Enable logging to .cmdorc/logs/cmdorc-tui.log",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="DEBUG",
        help="Set logging level (default: DEBUG)",
    )

    parser.add_argument(
        "--log-all",
        action="store_true",
        help="Also log cmdorc and textual-filelink packages",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Alias for --log-file (backward compatibility)",
    )

    return parser.parse_args()


def handle_list_configs() -> int:
    """
    List available named configs from cmdorc-tui.toml.

    Returns:
        Exit code (0 for success, 1 for no configs found)
    """
    discovery = discover_config()

    if discovery.mode == "multi" and discovery.config_set:
        print(f"Available configs (from {MULTI_CONFIG_FILENAME}):")
        default_name = discovery.config_set.get_default_config().name
        for config in discovery.config_set.configs:
            files = ", ".join(p.name for p in config.files)
            default_marker = " [default]" if config.name == default_name else ""
            print(f"  - {config.name} ({files}){default_marker}")
        return 0

    elif discovery.mode == "single" and discovery.single_config_path:
        print(f"Single config mode: {discovery.single_config_path.name}")
        print(f"  (Create {MULTI_CONFIG_FILENAME} for multi-config support)")
        return 0

    else:
        print("No configuration found.")
        print(f"  Run with --init-configs to generate {MULTI_CONFIG_FILENAME}")
        return 1


def handle_validate() -> int:
    """
    Validate cmdorc-tui.toml and check all referenced files exist.

    Returns:
        Exit code (0 for valid, 1 for errors)
    """
    discovery = discover_config()

    if discovery.mode != "multi":
        print(f"No {MULTI_CONFIG_FILENAME} found to validate.")
        return 1

    if discovery.error:
        print(f"Error loading {MULTI_CONFIG_FILENAME}: {discovery.error}")
        return 1

    if discovery.validation_errors:
        print(f"Validation errors in {MULTI_CONFIG_FILENAME}:")
        for error in discovery.validation_errors:
            print(f"  - Missing: {error.missing_path}")
            print(f"    Referenced in config: {error.config_name}")
        return 1

    print(f"{MULTI_CONFIG_FILENAME} is valid.")
    if discovery.config_set:
        print(f"  {len(discovery.config_set.configs)} config(s) defined")
    return 0


def handle_init_configs() -> int:
    """
    Auto-generate cmdorc-tui.toml from found TOML files.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    cwd = Path.cwd()
    meta_path = cwd / MULTI_CONFIG_FILENAME

    if meta_path.exists():
        print(f"{MULTI_CONFIG_FILENAME} already exists.")
        print("  Remove it first if you want to regenerate.")
        return 1

    toml_files = find_toml_files(cwd)

    if not toml_files:
        print("No TOML files found to generate config from.")
        print("  Create some .toml config files first.")
        return 1

    content = generate_cmdorc_tui_toml(toml_files, cwd)
    meta_path.write_text(content)

    print(f"Created {MULTI_CONFIG_FILENAME} with {len(toml_files)} config(s):")
    for f in toml_files:
        print(f"  - {f.name}")

    return 0


def main() -> None:
    """
    Main entry point for cmdorc-tui CLI.

    Handles:
    - Argument parsing
    - Logging configuration
    - Config discovery and resolution
    - Utility commands (--list-configs, --validate, --init-configs)
    - Launching CmdorcApp
    - Error handling and exit codes
    """
    args = parse_args()

    # Configure logging based on flags
    if args.log_file or args.verbose:
        from textual_cmdorc.logging import setup_logging

        setup_logging(level=args.log_level, log_all=args.log_all)

    try:
        # Handle utility commands first
        if args.list_configs:
            sys.exit(handle_list_configs())

        if args.validate:
            sys.exit(handle_validate())

        if args.init_configs:
            sys.exit(handle_init_configs())

        # Discover configs
        discovery = discover_config()

        # If explicit --config provided, use it
        if args.config:
            config_path = Path(args.config)
            # Check if it's a file path
            if config_path.exists() or config_path.suffix == ".toml":
                config_path = config_path.resolve()
                if not config_path.exists():
                    print(f"Error: Config file not found: {config_path}", file=sys.stderr)
                    sys.exit(1)
                app = CmdorcApp(config_path=str(config_path))
                app.run()
                return
            # Otherwise try to resolve as named config
            try:
                config_set, active_name, config_paths = resolve_startup_config(discovery, args.config)
                app = CmdorcApp(
                    config_paths=config_paths,
                    config_set=config_set,
                    active_config_name=active_name,
                )
                app.run()
                return
            except (FileNotFoundError, ValueError) as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

        # No explicit config - use discovery
        if discovery.mode == "none":
            # Show setup screen - let user choose what to create
            app = CmdorcApp(show_setup=True)
            app.run()
            return

        # Resolve startup config from discovery
        config_set, active_name, config_paths = resolve_startup_config(discovery)

        if not config_paths:
            print("Error: No config paths resolved", file=sys.stderr)
            sys.exit(1)

        # Launch app with resolved config
        app = CmdorcApp(
            config_paths=config_paths,
            config_set=config_set,
            active_config_name=active_name,
        )
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
