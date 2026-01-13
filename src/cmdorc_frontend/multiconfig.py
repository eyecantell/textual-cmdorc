"""Multi-config support for cmdorc-tui.

This module provides data models and parsing for the cmdorc-tui.toml
meta-config format, which allows users to define multiple named configurations.

Example cmdorc-tui.toml:
    [[config]]
    name = "Development"
    files = ["./commands.toml", "./build.toml", "./test.toml"]

    [[config]]
    name = "Build Only"
    files = ["./build.toml"]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore
from cmdorc import RunnerConfig, load_configs

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class ConfigParseError(Exception):
    """Error parsing cmdorc-tui.toml."""

    pass


class MissingConfigFileError(FileNotFoundError):
    """A referenced config file doesn't exist."""

    def __init__(self, config_name: str, missing_path: Path):
        self.config_name = config_name
        self.missing_path = missing_path
        super().__init__(f"Config '{config_name}' references missing file: {missing_path}")


class CircularIncludeError(ValueError):
    """Circular include dependency detected."""

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"Circular include: {' -> '.join(cycle)}")


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class NamedConfig:
    """A named configuration.

    Attributes:
        name: Display name (e.g., "Development")
        files: Config files to merge (in order)
        source_file: Path to cmdorc-tui.toml (for error messages)
    """

    name: str
    files: list[Path] = field(default_factory=list)
    source_file: Path = field(default_factory=lambda: Path("cmdorc-tui.toml"))

    def get_all_paths(self) -> list[Path]:
        """Return all config file paths."""
        return list(self.files)


@dataclass
class ConfigSet:
    """All configs from cmdorc-tui.toml.

    Attributes:
        configs: List of named configurations
        source_path: Path to cmdorc-tui.toml
    """

    configs: list[NamedConfig] = field(default_factory=list)
    source_path: Path = field(default_factory=lambda: Path("cmdorc-tui.toml"))

    def get_config_by_name(self, name: str) -> NamedConfig | None:
        """Look up config by name.

        Args:
            name: Config name to find

        Returns:
            NamedConfig if found, None otherwise
        """
        for config in self.configs:
            if config.name == name:
                return config
        return None

    def get_default_config(self) -> NamedConfig | None:
        """Get the default config (first one in file).

        Returns:
            First NamedConfig, or None if no configs defined
        """
        return self.configs[0] if self.configs else None

    def get_config_names(self) -> list[str]:
        """Return list of all config names.

        Returns:
            List of config names in definition order
        """
        return [c.name for c in self.configs]


# =============================================================================
# Parsing
# =============================================================================


def load_cmdorc_tui_toml(path: Path) -> ConfigSet:
    """Parse cmdorc-tui.toml and return ConfigSet.

    Args:
        path: Path to cmdorc-tui.toml

    Returns:
        ConfigSet with all named configurations

    Raises:
        FileNotFoundError: If cmdorc-tui.toml doesn't exist
        ConfigParseError: If TOML is invalid or missing required fields
        MissingConfigFileError: If a referenced config file doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigParseError(f"Invalid TOML in {path}: {e}") from e

    # Parse [[config]] entries
    config_entries = raw.get("config", [])
    if not config_entries:
        raise ConfigParseError(f"No [[config]] entries found in {path}. At least one configuration is required.")

    configs: list[NamedConfig] = []
    base_dir = path.parent

    for i, entry in enumerate(config_entries):
        # Validate required fields
        if "name" not in entry:
            raise ConfigParseError(f"[[config]] entry {i + 1} in {path} missing required 'name' field")

        name = entry["name"]
        files_raw = entry.get("files", [])

        if not files_raw:
            raise ConfigParseError(
                f"Config '{name}' in {path} has no 'files' specified. At least one config file is required."
            )

        # Resolve file paths relative to cmdorc-tui.toml location
        files: list[Path] = []
        for file_path in files_raw:
            resolved = (base_dir / Path(file_path)).resolve()
            files.append(resolved)

        configs.append(
            NamedConfig(
                name=name,
                files=files,
                source_file=path,
            )
        )

    logger.info(f"Loaded {len(configs)} config(s) from {path}")
    for config in configs:
        logger.debug(f"  - {config.name}: {[str(f) for f in config.files]}")

    return ConfigSet(configs=configs, source_path=path)


def validate_config_files(config_set: ConfigSet) -> list[MissingConfigFileError]:
    """Validate that all referenced config files exist.

    Args:
        config_set: ConfigSet to validate

    Returns:
        List of MissingConfigFileError for any missing files (empty if all exist)
    """
    errors: list[MissingConfigFileError] = []

    for config in config_set.configs:
        for file_path in config.files:
            if not file_path.exists():
                errors.append(MissingConfigFileError(config.name, file_path))

    return errors


# =============================================================================
# Loading with Source Tracking
# =============================================================================


def load_configs_with_sources(
    config_paths: list[Path],
) -> tuple[RunnerConfig, dict[str, Path]]:
    """Load multiple configs and track which file defined each command.

    Args:
        config_paths: Ordered list of config file paths

    Returns:
        Tuple of (merged_runner_config, command_to_source_map)
        The command_to_source_map maps command name -> source file path

    Raises:
        FileNotFoundError: If any config file doesn't exist
        cmdorc.ConfigValidationError: If duplicate command names found
    """
    command_sources: dict[str, Path] = {}

    # First pass: track which file defines each command
    for config_path in config_paths:
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigParseError(f"Invalid TOML in {config_path}: {e}") from e

        # Track command sources (first occurrence wins for display)
        for cmd_data in raw.get("command", []):
            cmd_name = cmd_data.get("name")
            if cmd_name and cmd_name not in command_sources:
                command_sources[cmd_name] = config_path

    # Second pass: use cmdorc's load_configs for actual merging
    # This handles variable merging, command validation, etc.
    logger.info(f"Loading {len(config_paths)} config file(s)")
    for p in config_paths:
        logger.debug(f"  - {p}")

    merged_config = load_configs(config_paths)

    return merged_config, command_sources
