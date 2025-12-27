"""Tests for formatting utilities."""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from textual_cmdorc.formatting import (
    format_elapsed_time,
    format_time_ago,
    get_output_preview,
    strip_ansi,
)


class TestFormatTimeAgo:
    """Tests for format_time_ago function."""

    def test_format_time_ago_none(self):
        """Test with None timestamp."""
        assert format_time_ago(None) == "?"

    def test_format_time_ago_just_now(self):
        """Test with very recent timestamp."""
        now = datetime.now()
        result = format_time_ago(now)
        assert result in ("just now", "0s ago")

    def test_format_time_ago_seconds(self):
        """Test with timestamp in seconds range."""
        timestamp = datetime.now() - timedelta(seconds=5)
        result = format_time_ago(timestamp)
        assert result == "5s ago"

    def test_format_time_ago_minutes(self):
        """Test with timestamp in minutes range."""
        timestamp = datetime.now() - timedelta(minutes=5)
        result = format_time_ago(timestamp)
        assert result == "5m ago"

    def test_format_time_ago_hours(self):
        """Test with timestamp in hours range."""
        timestamp = datetime.now() - timedelta(hours=2)
        result = format_time_ago(timestamp)
        assert result == "2h ago"

    def test_format_time_ago_days(self):
        """Test with timestamp in days range."""
        timestamp = datetime.now() - timedelta(days=3)
        result = format_time_ago(timestamp)
        assert result == "3d ago"

    def test_format_time_ago_float_timestamp(self):
        """Test with Unix float timestamp."""
        timestamp = (datetime.now() - timedelta(seconds=30)).timestamp()
        result = format_time_ago(timestamp)
        assert result in ("30s ago", "29s ago", "31s ago")  # Allow for timing variance

    def test_format_time_ago_invalid_type(self):
        """Test with invalid timestamp type."""
        result = format_time_ago("invalid")
        assert result == "?"


class TestFormatElapsedTime:
    """Tests for format_elapsed_time function."""

    def test_format_elapsed_time_seconds(self):
        """Test elapsed time in seconds."""
        start_time = datetime.now().timestamp() - 5
        result = format_elapsed_time(start_time)
        assert result in ("5s", "4s", "6s")  # Allow for timing variance

    def test_format_elapsed_time_minutes(self):
        """Test elapsed time in minutes."""
        start_time = datetime.now().timestamp() - 90
        result = format_elapsed_time(start_time)
        assert result in ("1m 30s", "1m 29s", "1m 31s")

    def test_format_elapsed_time_hours(self):
        """Test elapsed time in hours."""
        start_time = datetime.now().timestamp() - 3665
        result = format_elapsed_time(start_time)
        assert result in ("1h 1m", "1h 0m", "1h 2m")

    def test_format_elapsed_time_invalid(self):
        """Test with invalid start time."""
        result = format_elapsed_time("invalid")
        assert result == "?"


class TestStripAnsi:
    """Tests for strip_ansi function."""

    def test_strip_ansi_no_codes(self):
        """Test with text without ANSI codes."""
        text = "Hello, World!"
        assert strip_ansi(text) == "Hello, World!"

    def test_strip_ansi_with_color_codes(self):
        """Test with ANSI color codes."""
        text = "\x1b[31mRed text\x1b[0m"
        assert strip_ansi(text) == "Red text"

    def test_strip_ansi_with_bold(self):
        """Test with ANSI bold codes."""
        text = "\x1b[1mBold text\x1b[0m"
        assert strip_ansi(text) == "Bold text"

    def test_strip_ansi_multiple_codes(self):
        """Test with multiple ANSI codes."""
        text = "\x1b[1m\x1b[31mBold Red\x1b[0m Normal"
        assert strip_ansi(text) == "Bold Red Normal"

    def test_strip_ansi_empty_string(self):
        """Test with empty string."""
        assert strip_ansi("") == ""

    def test_strip_ansi_complex_escape_sequences(self):
        """Test with complex escape sequences."""
        text = "\x1b[38;5;214mOrange text\x1b[0m"
        assert strip_ansi(text) == "Orange text"


class TestGetOutputPreview:
    """Tests for get_output_preview function."""

    def test_get_output_preview_simple_file(self):
        """Test with a simple file."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Line 1\n")
            f.write("Line 2\n")
            f.write("Line 3\n")
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path, max_lines=5)
            assert total_lines == 3
            assert len(preview_lines) == 3
            assert preview_lines[0] == "Line 1"
            assert preview_lines[1] == "Line 2"
            assert preview_lines[2] == "Line 3"
        finally:
            file_path.unlink()

    def test_get_output_preview_truncate_lines(self):
        """Test that last N lines are returned."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            for i in range(10):
                f.write(f"Line {i}\n")
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path, max_lines=3)
            assert total_lines == 10
            assert len(preview_lines) == 3
            assert preview_lines[0] == "Line 7"
            assert preview_lines[1] == "Line 8"
            assert preview_lines[2] == "Line 9"
        finally:
            file_path.unlink()

    def test_get_output_preview_long_lines(self):
        """Test that long lines are truncated."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("a" * 100 + "\n")
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path, max_lines=5, max_line_length=60)
            assert total_lines == 1
            assert len(preview_lines) == 1
            assert preview_lines[0] == "a" * 60 + "..."
        finally:
            file_path.unlink()

    def test_get_output_preview_with_ansi_codes(self):
        """Test that ANSI codes are stripped."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("\x1b[31mRed line\x1b[0m\n")
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path)
            assert total_lines == 1
            assert preview_lines[0] == "Red line"
        finally:
            file_path.unlink()

    def test_get_output_preview_empty_file(self):
        """Test with empty file."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path)
            assert total_lines == 0
            assert len(preview_lines) == 0
        finally:
            file_path.unlink()

    def test_get_output_preview_nonexistent_file(self):
        """Test with nonexistent file."""
        result = get_output_preview(Path("/nonexistent/file.txt"))
        assert result is None

    def test_get_output_preview_custom_max_lines(self):
        """Test with custom max_lines parameter."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            for i in range(10):
                f.write(f"Line {i}\n")
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path, max_lines=2)
            assert total_lines == 10
            assert len(preview_lines) == 2
            assert preview_lines[0] == "Line 8"
            assert preview_lines[1] == "Line 9"
        finally:
            file_path.unlink()

    def test_get_output_preview_custom_max_line_length(self):
        """Test with custom max_line_length parameter."""
        with NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("a" * 100 + "\n")
            f.flush()
            file_path = Path(f.name)

        try:
            preview_lines, total_lines = get_output_preview(file_path, max_line_length=20)
            assert total_lines == 1
            assert preview_lines[0] == "a" * 20 + "..."
        finally:
            file_path.unlink()
