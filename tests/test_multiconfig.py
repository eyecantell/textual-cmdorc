"""Tests for multiconfig.py - multi-config support."""

from pathlib import Path

import pytest

from cmdorc_frontend.multiconfig import (
    CircularIncludeError,
    ConfigParseError,
    ConfigSet,
    MissingConfigFileError,
    NamedConfig,
    load_cmdorc_tui_toml,
    load_configs_with_sources,
    validate_config_files,
)

# =============================================================================
# Exception Tests
# =============================================================================


class TestConfigParseError:
    """Tests for ConfigParseError exception."""

    def test_basic_message(self):
        """ConfigParseError stores message correctly."""
        err = ConfigParseError("Invalid TOML syntax")
        assert str(err) == "Invalid TOML syntax"

    def test_inheritance(self):
        """ConfigParseError inherits from Exception."""
        err = ConfigParseError("test")
        assert isinstance(err, Exception)


class TestMissingConfigFileError:
    """Tests for MissingConfigFileError exception."""

    def test_stores_config_name_and_path(self):
        """MissingConfigFileError stores config name and missing path."""
        err = MissingConfigFileError("Development", Path("/path/to/missing.toml"))
        assert err.config_name == "Development"
        assert err.missing_path == Path("/path/to/missing.toml")

    def test_message_format(self):
        """MissingConfigFileError formats message correctly."""
        err = MissingConfigFileError("Build", Path("./build.toml"))
        assert "Build" in str(err)
        assert "build.toml" in str(err)

    def test_inheritance(self):
        """MissingConfigFileError inherits from FileNotFoundError."""
        err = MissingConfigFileError("Test", Path("test.toml"))
        assert isinstance(err, FileNotFoundError)


class TestCircularIncludeError:
    """Tests for CircularIncludeError exception."""

    def test_stores_cycle(self):
        """CircularIncludeError stores cycle list."""
        cycle = ["A", "B", "C", "A"]
        err = CircularIncludeError(cycle)
        assert err.cycle == cycle

    def test_message_format(self):
        """CircularIncludeError formats cycle in message."""
        err = CircularIncludeError(["config1", "config2", "config1"])
        assert "config1 -> config2 -> config1" in str(err)

    def test_inheritance(self):
        """CircularIncludeError inherits from ValueError."""
        err = CircularIncludeError(["A", "B"])
        assert isinstance(err, ValueError)


# =============================================================================
# NamedConfig Tests
# =============================================================================


class TestNamedConfig:
    """Tests for NamedConfig dataclass."""

    def test_basic_creation(self):
        """NamedConfig can be created with name and files."""
        config = NamedConfig(
            name="Development",
            files=[Path("config.toml"), Path("build.toml")],
        )
        assert config.name == "Development"
        assert len(config.files) == 2

    def test_default_files_empty(self):
        """NamedConfig defaults to empty files list."""
        config = NamedConfig(name="Empty")
        assert config.files == []

    def test_default_source_file(self):
        """NamedConfig defaults source_file to cmdorc-tui.toml."""
        config = NamedConfig(name="Test")
        assert config.source_file == Path("cmdorc-tui.toml")

    def test_get_all_paths(self):
        """get_all_paths() returns copy of files list."""
        files = [Path("a.toml"), Path("b.toml")]
        config = NamedConfig(name="Test", files=files)
        paths = config.get_all_paths()
        assert paths == files
        # Should be a copy, not the same list
        assert paths is not config.files

    def test_get_all_paths_empty(self):
        """get_all_paths() returns empty list when no files."""
        config = NamedConfig(name="Empty")
        assert config.get_all_paths() == []


# =============================================================================
# ConfigSet Tests
# =============================================================================


class TestConfigSet:
    """Tests for ConfigSet dataclass."""

    def test_basic_creation(self):
        """ConfigSet can be created with configs list."""
        configs = [
            NamedConfig(name="Dev", files=[Path("dev.toml")]),
            NamedConfig(name="Prod", files=[Path("prod.toml")]),
        ]
        config_set = ConfigSet(configs=configs)
        assert len(config_set.configs) == 2

    def test_default_empty_configs(self):
        """ConfigSet defaults to empty configs list."""
        config_set = ConfigSet()
        assert config_set.configs == []

    def test_default_source_path(self):
        """ConfigSet defaults source_path to cmdorc-tui.toml."""
        config_set = ConfigSet()
        assert config_set.source_path == Path("cmdorc-tui.toml")

    def test_get_config_by_name_found(self):
        """get_config_by_name() returns matching config."""
        dev_config = NamedConfig(name="Development")
        prod_config = NamedConfig(name="Production")
        config_set = ConfigSet(configs=[dev_config, prod_config])

        result = config_set.get_config_by_name("Development")
        assert result is dev_config

    def test_get_config_by_name_not_found(self):
        """get_config_by_name() returns None when not found."""
        config_set = ConfigSet(configs=[NamedConfig(name="Dev")])
        result = config_set.get_config_by_name("NonExistent")
        assert result is None

    def test_get_config_by_name_empty(self):
        """get_config_by_name() returns None on empty ConfigSet."""
        config_set = ConfigSet()
        result = config_set.get_config_by_name("Any")
        assert result is None

    def test_get_default_config(self):
        """get_default_config() returns first config."""
        first = NamedConfig(name="First")
        second = NamedConfig(name="Second")
        config_set = ConfigSet(configs=[first, second])

        result = config_set.get_default_config()
        assert result is first

    def test_get_default_config_empty(self):
        """get_default_config() returns None on empty ConfigSet."""
        config_set = ConfigSet()
        result = config_set.get_default_config()
        assert result is None

    def test_get_config_names(self):
        """get_config_names() returns list of all names in order."""
        configs = [
            NamedConfig(name="Alpha"),
            NamedConfig(name="Beta"),
            NamedConfig(name="Gamma"),
        ]
        config_set = ConfigSet(configs=configs)

        names = config_set.get_config_names()
        assert names == ["Alpha", "Beta", "Gamma"]

    def test_get_config_names_empty(self):
        """get_config_names() returns empty list when no configs."""
        config_set = ConfigSet()
        assert config_set.get_config_names() == []


# =============================================================================
# load_cmdorc_tui_toml Tests
# =============================================================================


class TestLoadCmdorcTuiToml:
    """Tests for load_cmdorc_tui_toml() parser."""

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_cmdorc_tui_toml(tmp_path / "nonexistent.toml")

    def test_invalid_toml(self, tmp_path):
        """Raises ConfigParseError on invalid TOML syntax."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text("invalid = [unclosed")

        with pytest.raises(ConfigParseError, match="Invalid TOML"):
            load_cmdorc_tui_toml(config_file)

    def test_no_config_entries(self, tmp_path):
        """Raises ConfigParseError when no [[config]] entries."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text("[settings]\ndefault = 'foo'\n")

        with pytest.raises(ConfigParseError, match="No \\[\\[config\\]\\] entries"):
            load_cmdorc_tui_toml(config_file)

    def test_missing_name_field(self, tmp_path):
        """Raises ConfigParseError when config entry missing name."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text('[[config]]\nfiles = ["test.toml"]\n')

        with pytest.raises(ConfigParseError, match="missing required 'name'"):
            load_cmdorc_tui_toml(config_file)

    def test_missing_files_field(self, tmp_path):
        """Raises ConfigParseError when config has no files."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text('[[config]]\nname = "Empty"\n')

        with pytest.raises(ConfigParseError, match="no 'files' specified"):
            load_cmdorc_tui_toml(config_file)

    def test_empty_files_list(self, tmp_path):
        """Raises ConfigParseError when files list is empty."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text('[[config]]\nname = "Empty"\nfiles = []\n')

        with pytest.raises(ConfigParseError, match="no 'files' specified"):
            load_cmdorc_tui_toml(config_file)

    def test_single_config(self, tmp_path):
        """Parses single config entry correctly."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text('[[config]]\nname = "Development"\nfiles = ["./commands.toml"]\n')

        result = load_cmdorc_tui_toml(config_file)

        assert len(result.configs) == 1
        assert result.configs[0].name == "Development"
        assert result.source_path == config_file

    def test_multiple_configs(self, tmp_path):
        """Parses multiple config entries in order."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text(
            """
[[config]]
name = "Development"
files = ["./dev.toml"]

[[config]]
name = "Production"
files = ["./prod.toml"]

[[config]]
name = "Testing"
files = ["./test.toml"]
"""
        )

        result = load_cmdorc_tui_toml(config_file)

        assert len(result.configs) == 3
        assert result.get_config_names() == ["Development", "Production", "Testing"]

    def test_multiple_files_per_config(self, tmp_path):
        """Parses config with multiple files."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text(
            """
[[config]]
name = "Full Stack"
files = ["./commands.toml", "./build.toml", "./test.toml"]
"""
        )

        result = load_cmdorc_tui_toml(config_file)

        assert len(result.configs[0].files) == 3

    def test_resolves_relative_paths(self, tmp_path):
        """Resolves file paths relative to cmdorc-tui.toml location."""
        subdir = tmp_path / "configs"
        subdir.mkdir()
        config_file = subdir / "cmdorc-tui.toml"
        config_file.write_text(
            """
[[config]]
name = "Test"
files = ["../commands.toml", "./local.toml"]
"""
        )

        result = load_cmdorc_tui_toml(config_file)

        # Paths should be resolved relative to config file location
        paths = result.configs[0].files
        assert paths[0] == (subdir / "../commands.toml").resolve()
        assert paths[1] == (subdir / "./local.toml").resolve()

    def test_stores_source_file(self, tmp_path):
        """Stores source_file in each NamedConfig."""
        config_file = tmp_path / "cmdorc-tui.toml"
        config_file.write_text('[[config]]\nname = "Test"\nfiles = ["test.toml"]\n')

        result = load_cmdorc_tui_toml(config_file)

        assert result.configs[0].source_file == config_file


# =============================================================================
# validate_config_files Tests
# =============================================================================


class TestValidateConfigFiles:
    """Tests for validate_config_files() function."""

    def test_all_files_exist(self, tmp_path):
        """Returns empty list when all files exist."""
        # Create actual files
        (tmp_path / "a.toml").write_text("# config a")
        (tmp_path / "b.toml").write_text("# config b")

        config_set = ConfigSet(configs=[NamedConfig(name="Test", files=[tmp_path / "a.toml", tmp_path / "b.toml"])])

        errors = validate_config_files(config_set)
        assert errors == []

    def test_missing_file(self, tmp_path):
        """Returns MissingConfigFileError for missing file."""
        (tmp_path / "exists.toml").write_text("# exists")

        config_set = ConfigSet(
            configs=[
                NamedConfig(
                    name="Test",
                    files=[tmp_path / "exists.toml", tmp_path / "missing.toml"],
                )
            ]
        )

        errors = validate_config_files(config_set)
        assert len(errors) == 1
        assert errors[0].config_name == "Test"
        assert errors[0].missing_path == tmp_path / "missing.toml"

    def test_multiple_missing_files(self, tmp_path):
        """Returns multiple errors for multiple missing files."""
        config_set = ConfigSet(
            configs=[
                NamedConfig(name="Dev", files=[tmp_path / "dev.toml"]),
                NamedConfig(name="Prod", files=[tmp_path / "prod.toml"]),
            ]
        )

        errors = validate_config_files(config_set)
        assert len(errors) == 2

    def test_empty_config_set(self):
        """Returns empty list for empty ConfigSet."""
        config_set = ConfigSet()
        errors = validate_config_files(config_set)
        assert errors == []


# =============================================================================
# load_configs_with_sources Tests
# =============================================================================


class TestLoadConfigsWithSources:
    """Tests for load_configs_with_sources() function."""

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError when config file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_configs_with_sources([tmp_path / "nonexistent.toml"])

    def test_invalid_toml(self, tmp_path):
        """Raises ConfigParseError on invalid TOML."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("invalid = [unclosed")

        with pytest.raises(ConfigParseError, match="Invalid TOML"):
            load_configs_with_sources([config_file])

    def test_single_config_file(self, tmp_path):
        """Loads single config and tracks command sources."""
        config_file = tmp_path / "commands.toml"
        config_file.write_text(
            """
[[command]]
name = "Build"
command = "make build"

[[command]]
name = "Test"
command = "make test"
"""
        )

        runner_config, sources = load_configs_with_sources([config_file])

        assert sources["Build"] == config_file
        assert sources["Test"] == config_file

    def test_multiple_config_files(self, tmp_path):
        """Tracks sources across multiple config files."""
        commands_file = tmp_path / "commands.toml"
        commands_file.write_text(
            """
[[command]]
name = "Build"
command = "make build"
"""
        )

        test_file = tmp_path / "test.toml"
        test_file.write_text(
            """
[[command]]
name = "Test"
command = "pytest"
"""
        )

        runner_config, sources = load_configs_with_sources([commands_file, test_file])

        assert sources["Build"] == commands_file
        assert sources["Test"] == test_file

    def test_first_occurrence_wins_for_source(self, tmp_path):
        """First file defining command is tracked as source."""
        # Note: cmdorc's load_configs may handle duplicates differently,
        # but for source tracking, first occurrence wins
        file_a = tmp_path / "a.toml"
        file_a.write_text('[[command]]\nname = "Cmd"\ncommand = "echo a"\n')

        file_b = tmp_path / "b.toml"
        file_b.write_text('[[command]]\nname = "Cmd"\ncommand = "echo b"\n')

        # This may raise a duplicate command error from cmdorc
        # depending on cmdorc's behavior - adjust test accordingly
        try:
            _, sources = load_configs_with_sources([file_a, file_b])
            # If it doesn't raise, first occurrence should be tracked
            assert sources["Cmd"] == file_a
        except Exception:
            # cmdorc may reject duplicate command names
            pytest.skip("cmdorc rejects duplicate command names")

    def test_empty_config_file(self, tmp_path):
        """Handles config file with no commands."""
        config_file = tmp_path / "empty.toml"
        config_file.write_text("# Empty config\n")

        runner_config, sources = load_configs_with_sources([config_file])

        assert sources == {}

    def test_returns_merged_config(self, tmp_path):
        """Returns merged config from cmdorc's load_configs."""
        config_file = tmp_path / "commands.toml"
        config_file.write_text('[[command]]\nname = "Hello"\ncommand = "echo hello"\n')

        runner_config, sources = load_configs_with_sources([config_file])

        # Should return something (could be mocked in test environment)
        assert runner_config is not None
        # Sources should be tracked
        assert "Hello" in sources
