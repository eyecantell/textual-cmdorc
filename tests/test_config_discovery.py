"""Tests for config_discovery.py."""

import pytest

from cmdorc_frontend.config_discovery import (
    MULTI_CONFIG_FILENAME,
    ConfigDiscoveryResult,
    discover_config,
    find_toml_files,
    generate_cmdorc_tui_toml,
    is_valid_cmdorc_config,
    resolve_startup_config,
)
from cmdorc_frontend.multiconfig import ConfigSet, NamedConfig

# =============================================================================
# discover_config Tests
# =============================================================================


class TestDiscoverConfig:
    """Tests for discover_config function."""

    def test_finds_multi_config(self, tmp_path):
        """discover_config finds cmdorc-tui.toml first."""
        # Create cmdorc-tui.toml
        meta_config = tmp_path / MULTI_CONFIG_FILENAME
        meta_config.write_text('[[config]]\nname = "Test"\nfiles = ["./test.toml"]\n')
        # Also create commands.toml (should be ignored)
        (tmp_path / "commands.toml").write_text("# ignored\n")

        result = discover_config(tmp_path)

        assert result.mode == "multi"
        assert result.config_set is not None
        assert result.single_config_path is None

    def test_finds_commands_toml(self, tmp_path):
        """discover_config finds commands.toml when no cmdorc-tui.toml."""
        (tmp_path / "commands.toml").write_text('[[command]]\nname = "Test"\ncommand = "echo test"\n')

        result = discover_config(tmp_path)

        assert result.mode == "single"
        assert result.single_config_path == tmp_path / "commands.toml"
        assert result.config_set is None

    def test_finds_config_toml_fallback(self, tmp_path):
        """discover_config falls back to config.toml."""
        (tmp_path / "config.toml").write_text('[[command]]\nname = "Test"\ncommand = "echo test"\n')

        result = discover_config(tmp_path)

        assert result.mode == "single"
        assert result.single_config_path == tmp_path / "config.toml"

    def test_commands_toml_priority_over_config_toml(self, tmp_path):
        """commands.toml takes priority over config.toml."""
        (tmp_path / "commands.toml").write_text("# commands\n")
        (tmp_path / "config.toml").write_text("# config\n")

        result = discover_config(tmp_path)

        assert result.mode == "single"
        assert result.single_config_path.name == "commands.toml"

    def test_returns_none_when_no_config(self, tmp_path):
        """discover_config returns mode='none' when no configs found."""
        result = discover_config(tmp_path)

        assert result.mode == "none"
        assert result.config_set is None
        assert result.single_config_path is None

    def test_validation_errors_for_missing_files(self, tmp_path):
        """discover_config reports validation errors for missing files."""
        meta_config = tmp_path / MULTI_CONFIG_FILENAME
        meta_config.write_text('[[config]]\nname = "Test"\nfiles = ["./missing.toml"]\n')

        result = discover_config(tmp_path)

        assert result.mode == "multi"
        assert len(result.validation_errors) == 1
        assert "missing.toml" in str(result.validation_errors[0].missing_path)

    def test_uses_cwd_when_path_not_specified(self, tmp_path, monkeypatch):
        """discover_config uses cwd when path not specified."""
        (tmp_path / "commands.toml").write_text("# test\n")
        monkeypatch.chdir(tmp_path)

        result = discover_config()

        assert result.mode == "single"


# =============================================================================
# resolve_startup_config Tests
# =============================================================================


class TestResolveStartupConfig:
    """Tests for resolve_startup_config function."""

    def test_uses_default_multi_config(self, tmp_path):
        """resolve_startup_config uses first config as default."""
        # Create valid config files
        (tmp_path / "dev.toml").write_text('[[command]]\nname = "Dev"\ncommand = "echo dev"\n')
        (tmp_path / "prod.toml").write_text('[[command]]\nname = "Prod"\ncommand = "echo prod"\n')

        config_set = ConfigSet(
            configs=[
                NamedConfig(name="Development", files=[tmp_path / "dev.toml"]),
                NamedConfig(name="Production", files=[tmp_path / "prod.toml"]),
            ]
        )
        discovery = ConfigDiscoveryResult(mode="multi", config_set=config_set)

        result_set, active_name, paths = resolve_startup_config(discovery)

        assert result_set is config_set
        assert active_name == "Development"
        assert paths == [tmp_path / "dev.toml"]

    def test_uses_single_config(self, tmp_path):
        """resolve_startup_config uses single config path."""
        config_path = tmp_path / "commands.toml"
        discovery = ConfigDiscoveryResult(
            mode="single",
            single_config_path=config_path,
        )

        result_set, active_name, paths = resolve_startup_config(discovery)

        assert result_set is None
        assert active_name is None
        assert paths == [config_path]

    def test_returns_empty_when_no_config(self):
        """resolve_startup_config returns empty list when no config."""
        discovery = ConfigDiscoveryResult(mode="none")

        result_set, active_name, paths = resolve_startup_config(discovery)

        assert result_set is None
        assert active_name is None
        assert paths == []

    def test_cli_selects_named_config(self, tmp_path):
        """CLI --config selects named config from multi-config."""
        (tmp_path / "prod.toml").write_text('[[command]]\nname = "Prod"\ncommand = "echo prod"\n')

        config_set = ConfigSet(
            configs=[
                NamedConfig(name="Development", files=[tmp_path / "dev.toml"]),
                NamedConfig(name="Production", files=[tmp_path / "prod.toml"]),
            ]
        )
        discovery = ConfigDiscoveryResult(mode="multi", config_set=config_set)

        result_set, active_name, paths = resolve_startup_config(discovery, cli_config_arg="Production")

        assert active_name == "Production"
        assert paths == [tmp_path / "prod.toml"]

    def test_cli_selects_file_path(self, tmp_path):
        """CLI --config can specify a file path directly."""
        config_path = tmp_path / "custom.toml"
        config_path.write_text('[[command]]\nname = "Custom"\ncommand = "echo custom"\n')

        discovery = ConfigDiscoveryResult(mode="none")

        result_set, active_name, paths = resolve_startup_config(discovery, cli_config_arg=str(config_path))

        assert result_set is None
        assert active_name is None
        assert paths == [config_path]

    def test_cli_file_not_found_raises(self, tmp_path):
        """CLI --config with missing file raises FileNotFoundError."""
        discovery = ConfigDiscoveryResult(mode="none")

        with pytest.raises(FileNotFoundError):
            resolve_startup_config(discovery, cli_config_arg="nonexistent.toml")

    def test_cli_named_config_not_found_raises(self, tmp_path):
        """CLI --config with unknown named config raises ValueError."""
        config_set = ConfigSet(
            configs=[
                NamedConfig(name="Development", files=[tmp_path / "dev.toml"]),
            ]
        )
        discovery = ConfigDiscoveryResult(mode="multi", config_set=config_set)

        with pytest.raises(ValueError, match="Available named configs"):
            resolve_startup_config(discovery, cli_config_arg="NonExistent")


# =============================================================================
# find_toml_files Tests
# =============================================================================


class TestFindTomlFiles:
    """Tests for find_toml_files function."""

    def test_finds_all_toml_files(self, tmp_path):
        """find_toml_files finds all TOML files."""
        (tmp_path / "a.toml").write_text("# a\n")
        (tmp_path / "b.toml").write_text("# b\n")
        (tmp_path / "c.txt").write_text("# not toml\n")

        result = find_toml_files(tmp_path, validate=False)

        assert len(result) == 2
        assert all(f.suffix == ".toml" for f in result)

    def test_excludes_meta_config_by_default(self, tmp_path):
        """find_toml_files excludes cmdorc-tui.toml by default."""
        (tmp_path / MULTI_CONFIG_FILENAME).write_text("# meta\n")
        (tmp_path / "commands.toml").write_text("# commands\n")

        result = find_toml_files(tmp_path, validate=False)

        assert len(result) == 1
        assert result[0].name == "commands.toml"

    def test_includes_meta_config_when_requested(self, tmp_path):
        """find_toml_files includes cmdorc-tui.toml when exclude_meta=False."""
        (tmp_path / MULTI_CONFIG_FILENAME).write_text("# meta\n")
        (tmp_path / "commands.toml").write_text("# commands\n")

        result = find_toml_files(tmp_path, exclude_meta=False, validate=False)

        assert len(result) == 2

    def test_returns_sorted(self, tmp_path):
        """find_toml_files returns files sorted by name."""
        (tmp_path / "z.toml").write_text("# z\n")
        (tmp_path / "a.toml").write_text("# a\n")
        (tmp_path / "m.toml").write_text("# m\n")

        result = find_toml_files(tmp_path, validate=False)

        assert [f.name for f in result] == ["a.toml", "m.toml", "z.toml"]

    def test_returns_empty_when_no_files(self, tmp_path):
        """find_toml_files returns empty list when no TOML files."""
        result = find_toml_files(tmp_path)
        assert result == []


# =============================================================================
# is_valid_cmdorc_config Tests
# =============================================================================


class TestIsValidCmdorcConfig:
    """Tests for is_valid_cmdorc_config function."""

    def test_valid_minimal_config(self, tmp_path):
        """Minimal valid config with one command."""
        config = tmp_path / "valid.toml"
        config.write_text("""
[[command]]
name = "Test"
command = "echo test"
""")
        assert is_valid_cmdorc_config(config) is True

    def test_valid_full_config(self, tmp_path):
        """Full valid config with all sections."""
        config = tmp_path / "full.toml"
        config.write_text("""
[variables]
base_dir = "."

[[command]]
name = "Lint"
command = "ruff check ."
triggers = ["file_changed"]

[[file_watcher]]
dir = "."
extensions = [".py"]
trigger_emitted = "file_changed"

[keyboard]
shortcuts = { Lint = "1" }
""")
        assert is_valid_cmdorc_config(config) is True

    def test_invalid_pyproject_toml(self, tmp_path):
        """pyproject.toml is not a valid cmdorc config."""
        config = tmp_path / "pyproject.toml"
        config.write_text("""
[project]
name = "my-project"
version = "1.0.0"
""")
        assert is_valid_cmdorc_config(config) is False

    def test_invalid_no_commands(self, tmp_path):
        """Config without [[command]] section is invalid."""
        config = tmp_path / "no_commands.toml"
        config.write_text("""
[variables]
base_dir = "."
""")
        assert is_valid_cmdorc_config(config) is False

    def test_invalid_command_missing_required_fields(self, tmp_path):
        """Command without name or command field is invalid."""
        config = tmp_path / "incomplete.toml"
        config.write_text("""
[[command]]
name = "Test"
# Missing 'command' field
""")
        assert is_valid_cmdorc_config(config) is False

    def test_invalid_toml_syntax(self, tmp_path):
        """Malformed TOML returns False."""
        config = tmp_path / "bad.toml"
        config.write_text("this is not [[[valid toml")
        assert is_valid_cmdorc_config(config) is False

    def test_file_not_found(self, tmp_path):
        """Non-existent file returns False."""
        config = tmp_path / "nonexistent.toml"
        assert is_valid_cmdorc_config(config) is False


# =============================================================================
# find_toml_files Validation Tests
# =============================================================================


class TestFindTomlFilesValidation:
    """Tests for find_toml_files with validation."""

    def test_filters_invalid_toml_by_default(self, tmp_path):
        """find_toml_files filters out non-cmdorc TOML files by default."""
        # Valid cmdorc config
        (tmp_path / "commands.toml").write_text("""
[[command]]
name = "Test"
command = "echo test"
""")
        # Invalid configs
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "other.toml").write_text("[settings]\nfoo = 'bar'\n")

        result = find_toml_files(tmp_path)

        assert len(result) == 1
        assert result[0].name == "commands.toml"

    def test_includes_all_when_validation_disabled(self, tmp_path):
        """find_toml_files includes all TOML when validate=False."""
        (tmp_path / "commands.toml").write_text("[[command]]\nname='Test'\ncommand='echo'\n")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        result = find_toml_files(tmp_path, validate=False)

        assert len(result) == 2
        assert {f.name for f in result} == {"commands.toml", "pyproject.toml"}

    def test_multiple_valid_configs(self, tmp_path):
        """find_toml_files finds multiple valid configs."""
        for name in ["build.toml", "test.toml", "dev.toml"]:
            (tmp_path / name).write_text(f"[[command]]\nname='{name}'\ncommand='echo'\n")

        (tmp_path / "invalid.toml").write_text("[project]\nname='test'\n")

        result = find_toml_files(tmp_path)

        assert len(result) == 3
        assert {f.name for f in result} == {"build.toml", "test.toml", "dev.toml"}


# =============================================================================
# generate_cmdorc_tui_toml Tests
# =============================================================================


class TestGenerateCmdorcTuiToml:
    """Tests for generate_cmdorc_tui_toml function."""

    def test_generates_single_config(self, tmp_path):
        """generate_cmdorc_tui_toml generates config for single file."""
        config_file = tmp_path / "commands.toml"

        result = generate_cmdorc_tui_toml([config_file], tmp_path)

        assert "[[config]]" in result
        assert 'name = "Commands"' in result
        assert 'files = ["./commands.toml"]' in result

    def test_generates_all_configs_when_multiple(self, tmp_path):
        """generate_cmdorc_tui_toml generates 'All Configs' for multiple files."""
        files = [
            tmp_path / "build.toml",
            tmp_path / "test.toml",
        ]

        result = generate_cmdorc_tui_toml(files, tmp_path)

        assert 'name = "All Configs"' in result
        assert "./build.toml" in result
        assert "./test.toml" in result

    def test_creates_individual_configs(self, tmp_path):
        """generate_cmdorc_tui_toml creates individual config for each file."""
        files = [
            tmp_path / "build.toml",
            tmp_path / "test-commands.toml",
        ]

        result = generate_cmdorc_tui_toml(files, tmp_path)

        assert 'name = "Build"' in result
        assert 'name = "Test Commands"' in result

    def test_includes_header_comment(self, tmp_path):
        """generate_cmdorc_tui_toml includes header comment."""
        result = generate_cmdorc_tui_toml([tmp_path / "test.toml"], tmp_path)

        assert "Generated by cmdorc-tui" in result
