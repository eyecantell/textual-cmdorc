"""Config discovery for startup config detection.

This module provides discovery logic for finding and loading
configuration files at startup. It supports:
- Multi-config via cmdorc-tui.toml
- Single-config via commands.toml (preferred) or config.toml (legacy)
- Graceful handling when no configs found
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from cmdorc_frontend.multiconfig import (
    ConfigSet,
    MissingConfigFileError,
    load_cmdorc_tui_toml,
    validate_config_files,
)

logger = logging.getLogger(__name__)


# Standard config file names in priority order
MULTI_CONFIG_FILENAME = "cmdorc-tui.toml"
SINGLE_CONFIG_FILENAMES = ["commands.toml", "config.toml"]


@dataclass
class ConfigDiscoveryResult:
    """Result of config discovery.

    Attributes:
        mode: Discovery mode - "multi", "single", or "none"
        config_set: ConfigSet when mode="multi"
        single_config_path: Path when mode="single"
        error: Error message if discovery failed
        validation_errors: List of missing file errors for multi-config
    """

    mode: Literal["multi", "single", "none"]
    config_set: ConfigSet | None = None
    single_config_path: Path | None = None
    error: str | None = None
    validation_errors: list[MissingConfigFileError] = field(default_factory=list)


def discover_config(cwd: Path | None = None) -> ConfigDiscoveryResult:
    """Discover configs in priority order.

    Priority:
    1. cmdorc-tui.toml (multi-config mode)
    2. commands.toml (single-config, preferred)
    3. config.toml (single-config, legacy fallback)
    4. None (no config found)

    Args:
        cwd: Working directory to search in (defaults to current directory)

    Returns:
        ConfigDiscoveryResult with discovery outcome
    """
    if cwd is None:
        cwd = Path.cwd()

    cwd = Path(cwd).resolve()
    logger.debug(f"Discovering config in: {cwd}")

    # Check for multi-config first
    multi_config_path = cwd / MULTI_CONFIG_FILENAME
    if multi_config_path.exists():
        logger.info(f"Found multi-config: {multi_config_path}")
        return _load_multi_config(multi_config_path)

    # Check for single-config files in priority order
    for filename in SINGLE_CONFIG_FILENAMES:
        single_path = cwd / filename
        if single_path.exists():
            logger.info(f"Found single-config: {single_path}")
            return ConfigDiscoveryResult(
                mode="single",
                single_config_path=single_path,
            )

    # No config found
    logger.info("No config found")
    return ConfigDiscoveryResult(mode="none")


def _load_multi_config(path: Path) -> ConfigDiscoveryResult:
    """Load and validate multi-config file.

    Args:
        path: Path to cmdorc-tui.toml

    Returns:
        ConfigDiscoveryResult with loaded ConfigSet or error
    """
    try:
        config_set = load_cmdorc_tui_toml(path)

        # Validate all referenced files exist
        validation_errors = validate_config_files(config_set)

        if validation_errors:
            # Return with validation errors but still usable
            logger.warning(f"Multi-config has {len(validation_errors)} missing file(s)")
            return ConfigDiscoveryResult(
                mode="multi",
                config_set=config_set,
                validation_errors=validation_errors,
            )

        return ConfigDiscoveryResult(
            mode="multi",
            config_set=config_set,
        )

    except FileNotFoundError as e:
        return ConfigDiscoveryResult(
            mode="none",
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to load {path}: {e}")
        return ConfigDiscoveryResult(
            mode="none",
            error=str(e),
        )


def resolve_startup_config(
    discovery: ConfigDiscoveryResult,
    cli_config_arg: str | None = None,
) -> tuple[ConfigSet | None, str | None, list[Path]]:
    """Resolve which config(s) to load at startup.

    Handles CLI argument override and config selection.

    Args:
        discovery: Result from discover_config()
        cli_config_arg: Optional --config argument from CLI

    Returns:
        Tuple of (config_set, active_config_name, config_paths)
        - config_set: ConfigSet if multi-config, None otherwise
        - active_config_name: Name of active config if multi-config
        - config_paths: List of config file paths to load

    Raises:
        FileNotFoundError: If specified config not found
        ValueError: If specified named config doesn't exist
    """
    # Handle CLI override
    if cli_config_arg:
        return _resolve_cli_config(discovery, cli_config_arg)

    # Handle discovery result
    if discovery.mode == "multi" and discovery.config_set:
        # Use default (first) config from multi-config
        default_config = discovery.config_set.get_default_config()
        if default_config:
            return (
                discovery.config_set,
                default_config.name,
                default_config.get_all_paths(),
            )
        # No configs in ConfigSet (shouldn't happen with valid file)
        raise ValueError("No configurations defined in cmdorc-tui.toml")

    elif discovery.mode == "single" and discovery.single_config_path:
        return (None, None, [discovery.single_config_path])

    else:
        # No config found
        return (None, None, [])


def _resolve_cli_config(
    discovery: ConfigDiscoveryResult,
    cli_arg: str,
) -> tuple[ConfigSet | None, str | None, list[Path]]:
    """Resolve CLI --config argument.

    The argument can be:
    - A named config from cmdorc-tui.toml (e.g., "Development")
    - A direct file path (e.g., "./my-config.toml")

    Args:
        discovery: Result from discover_config()
        cli_arg: The --config argument value

    Returns:
        Tuple of (config_set, active_config_name, config_paths)

    Raises:
        FileNotFoundError: If specified file doesn't exist
        ValueError: If specified named config doesn't exist
    """
    # Check if it's a named config from multi-config
    if discovery.mode == "multi" and discovery.config_set:
        named_config = discovery.config_set.get_config_by_name(cli_arg)
        if named_config:
            logger.info(f"Using named config: {cli_arg}")
            return (
                discovery.config_set,
                cli_arg,
                named_config.get_all_paths(),
            )

    # Treat as file path
    config_path = Path(cli_arg)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    if not config_path.exists():
        # Check if user meant a named config but it doesn't exist
        if discovery.mode == "multi" and discovery.config_set:
            available = discovery.config_set.get_config_names()
            raise ValueError(f"Config '{cli_arg}' not found. Available named configs: {', '.join(available)}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.info(f"Using config file: {config_path}")
    return (None, None, [config_path])


def is_valid_cmdorc_config(path: Path) -> bool:
    """Check if a TOML file is a valid cmdorc configuration.

    A valid cmdorc config must have at least one [[command]] section.

    Args:
        path: Path to TOML file to validate

    Returns:
        True if file is a valid cmdorc config, False otherwise
    """
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)

        # Must have at least one [[command]] entry
        commands = data.get("command", [])
        if not commands:
            return False

        # Each command must have required fields
        for cmd in commands:
            if not isinstance(cmd, dict):
                return False
            if "name" not in cmd or "command" not in cmd:
                return False

        return True

    except Exception:
        # Failed to parse or read - not a valid config
        return False


def find_toml_files(
    cwd: Path | None = None,
    exclude_meta: bool = True,
    validate: bool = True,
) -> list[Path]:
    """Find all TOML files in directory for init-configs command.

    Args:
        cwd: Directory to search (defaults to current directory)
        exclude_meta: Whether to exclude cmdorc-tui.toml
        validate: Whether to validate files as cmdorc configs (default True)

    Returns:
        List of found TOML file paths, sorted by name
    """
    if cwd is None:
        cwd = Path.cwd()

    cwd = Path(cwd).resolve()
    toml_files = sorted(cwd.glob("*.toml"))

    if exclude_meta:
        toml_files = [f for f in toml_files if f.name != MULTI_CONFIG_FILENAME]

    # Filter out non-cmdorc TOML files
    if validate:
        toml_files = [f for f in toml_files if is_valid_cmdorc_config(f)]

    return toml_files


def generate_cmdorc_tui_toml(toml_files: list[Path], cwd: Path | None = None) -> str:
    """Generate cmdorc-tui.toml content from found TOML files.

    Creates a template with:
    - "All Configs" - includes all found files
    - Individual configs for each file

    Args:
        toml_files: List of TOML files to include
        cwd: Base directory for relative paths

    Returns:
        TOML content string
    """
    if cwd is None:
        cwd = Path.cwd()

    cwd = Path(cwd).resolve()

    lines = ["# Generated by cmdorc-tui --init-configs", ""]

    # Create "All" config if multiple files
    if len(toml_files) > 1:
        lines.append("[[config]]")
        lines.append('name = "All Configs"')
        files_str = ", ".join(f'"./{f.relative_to(cwd)}"' for f in toml_files)
        lines.append(f"files = [{files_str}]")
        lines.append("")

    # Create individual configs
    for toml_file in toml_files:
        name = toml_file.stem.replace("-", " ").replace("_", " ").title()
        lines.append("[[config]]")
        lines.append(f'name = "{name}"')
        lines.append(f'files = ["./{toml_file.relative_to(cwd)}"]')
        lines.append("")

    return "\n".join(lines)
