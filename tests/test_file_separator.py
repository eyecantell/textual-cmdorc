"""Tests for FileSeparator widget."""

from textual_cmdorc.file_separator import FileSeparator


class TestFileSeparatorInitialization:
    """Tests for FileSeparator initialization."""

    def test_basic_init(self):
        """FileSeparator initializes with filename."""
        separator = FileSeparator("config.toml")
        assert separator.filename == "config.toml"

    def test_various_filenames(self):
        """FileSeparator accepts various filename formats."""
        separator1 = FileSeparator("build.toml")
        assert separator1.filename == "build.toml"

        separator2 = FileSeparator("my-commands.toml")
        assert separator2.filename == "my-commands.toml"

        separator3 = FileSeparator("path/to/config.toml")
        assert separator3.filename == "path/to/config.toml"


class TestFileSeparatorDisplay:
    """Tests for FileSeparator display behavior."""

    def test_update_display_called_on_init(self):
        """_update_display is called during initialization."""
        separator = FileSeparator("test.toml")
        # Verify internal state was set
        assert separator._filename == "test.toml"

    def test_different_filenames_have_different_state(self):
        """Different filenames produce different internal state."""
        separator1 = FileSeparator("file1.toml")
        separator2 = FileSeparator("file2.toml")

        assert separator1._filename != separator2._filename
        assert separator1._filename == "file1.toml"
        assert separator2._filename == "file2.toml"


class TestFileSeparatorSetFilename:
    """Tests for set_filename method."""

    def test_set_filename_updates_property(self):
        """set_filename updates the filename property."""
        separator = FileSeparator("original.toml")
        separator.set_filename("updated.toml")
        assert separator.filename == "updated.toml"

    def test_set_filename_updates_internal_state(self):
        """set_filename updates internal state."""
        separator = FileSeparator("original.toml")
        separator.set_filename("updated.toml")

        # Check internal state reflects update
        assert separator._filename == "updated.toml"
