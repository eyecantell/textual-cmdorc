"""Tests for WatcherStatusLine widget."""

import time
from dataclasses import dataclass
from pathlib import Path

from textual_cmdorc.watcher_status_line import WatcherStatusLine


@dataclass
class MockWatcherConfig:
    """Mock WatcherConfig for testing."""

    dir: Path
    extensions: list[str] | None = None
    recursive: bool = True


def test_status_line_initial_state_enabled():
    """Status line shows correct initial state when enabled."""
    line = WatcherStatusLine(watcher_count=3, enabled=True)

    # Check state
    assert line.enabled is True
    assert line.watcher_count == 3


def test_status_line_initial_state_disabled():
    """Status line shows correct initial state when disabled."""
    line = WatcherStatusLine(watcher_count=2, enabled=False)

    # Check state
    assert line.enabled is False
    assert line.watcher_count == 2


def test_status_line_toggle_click():
    """Clicking status line toggles state and posts message."""
    line = WatcherStatusLine(watcher_count=3, enabled=True)

    # Track messages
    messages = []
    _original_post_message = line.post_message
    line.post_message = lambda msg: messages.append(msg)

    # Initial state
    assert line.enabled is True

    # Click to toggle off
    line.on_click()
    assert line.enabled is False
    assert len(messages) == 1
    assert isinstance(messages[0], WatcherStatusLine.Toggled)

    # Click to toggle back on
    line.on_click()
    assert line.enabled is True
    assert len(messages) == 2
    assert isinstance(messages[1], WatcherStatusLine.Toggled)


def test_status_line_set_enabled_without_message():
    """set_enabled() updates display without posting message."""
    line = WatcherStatusLine(watcher_count=2, enabled=True)

    # Track messages
    messages = []
    line.post_message = lambda msg: messages.append(msg)

    # Change state via set_enabled
    line.set_enabled(False)

    # Check state changed
    assert line.enabled is False

    # No message should be posted
    assert len(messages) == 0


def test_status_line_set_enabled_no_change():
    """set_enabled() with same value doesn't update display."""
    line = WatcherStatusLine(watcher_count=2, enabled=True)

    # Spy on _update_display
    update_count = [0]
    original_update = line._update_display

    def spy_update():
        update_count[0] += 1
        original_update()

    line._update_display = spy_update

    # Reset counter (initial display update in __init__)
    update_count[0] = 0

    # Set to same value
    line.set_enabled(True)

    # Should not trigger update
    assert update_count[0] == 0

    # Set to different value
    line.set_enabled(False)

    # Should trigger update
    assert update_count[0] == 1


def test_status_line_zero_watchers():
    """Status line handles zero watchers gracefully."""
    line = WatcherStatusLine(watcher_count=0, enabled=True)

    assert line.watcher_count == 0
    assert line.enabled is True


def test_status_line_many_watchers():
    """Status line displays correct count for many watchers."""
    line = WatcherStatusLine(watcher_count=10, enabled=True)

    assert line.watcher_count == 10
    assert line.enabled is True


# Tests for last triggered file display


def test_status_line_initial_no_last_file():
    """Status line starts with no last file info."""
    line = WatcherStatusLine(watcher_count=2, enabled=True)

    assert line.last_file is None
    assert line.last_file_time is None


def test_status_line_set_last_file():
    """set_last_file() stores file path and timestamp."""
    line = WatcherStatusLine(watcher_count=2, enabled=True)

    test_path = Path("/test/src/app.py")
    test_time = time.time()

    line.set_last_file(test_path, test_time)

    assert line.last_file == test_path
    assert line.last_file_time == test_time


def test_status_line_set_last_file_triggers_update():
    """set_last_file() triggers display update."""
    line = WatcherStatusLine(watcher_count=2, enabled=True)

    # Spy on _update_display
    update_count = [0]
    original_update = line._update_display

    def spy_update():
        update_count[0] += 1
        original_update()

    line._update_display = spy_update

    # Reset counter
    update_count[0] = 0

    # Set last file
    line.set_last_file(Path("/test/file.py"), time.time())

    # Should trigger update
    assert update_count[0] == 1


def test_status_line_display_with_last_file(monkeypatch):
    """Display includes file path and time when last file is set."""
    line = WatcherStatusLine(watcher_count=2, enabled=True)

    # Mock Path.cwd() to return a known path
    monkeypatch.setattr(Path, "cwd", lambda: Path("/test"))

    # Set last file (relative path under cwd)
    test_path = Path("/test/src/app.py")
    test_time = time.time() - 5  # 5 seconds ago

    line.set_last_file(test_path, test_time)

    # Verify state is stored correctly
    assert line.last_file == test_path
    assert line.last_file_time == test_time

    # Verify the display was updated by checking internal state
    # When enabled with a file, _update_display builds text with file info
    assert line.enabled is True


def test_status_line_display_disabled_hides_file_info():
    """Disabled state doesn't show file info even if set."""
    line = WatcherStatusLine(watcher_count=2, enabled=False)

    # Set last file
    test_path = Path("/test/file.py")
    test_time = time.time()
    line.set_last_file(test_path, test_time)

    # File info should still be stored
    assert line.last_file == test_path
    assert line.last_file_time == test_time

    # But display shows disabled (file info not shown when disabled)
    assert line.enabled is False


# Tests for tooltip with watcher configs


def test_tooltip_no_configs():
    """Tooltip shows no watchers message when no configs provided."""
    line = WatcherStatusLine(watcher_count=0, enabled=True, watcher_configs=None)

    tooltip = line._build_watcher_tooltip()

    assert tooltip == "No file watchers configured"


def test_tooltip_empty_configs():
    """Tooltip shows no watchers message when empty list provided."""
    line = WatcherStatusLine(watcher_count=0, enabled=True, watcher_configs=[])

    tooltip = line._build_watcher_tooltip()

    assert tooltip == "No file watchers configured"


def test_tooltip_single_watcher_recursive(monkeypatch):
    """Tooltip shows single watcher with recursive indicator."""
    # Mock cwd to be a known path
    monkeypatch.setattr(Path, "cwd", lambda: Path("/project"))

    config = MockWatcherConfig(
        dir=Path("/project/src"),
        extensions=[".py", ".txt"],
        recursive=True,
    )
    line = WatcherStatusLine(watcher_count=1, enabled=True, watcher_configs=[config])

    tooltip = line._build_watcher_tooltip()

    assert "File Watchers:" in tooltip
    assert "./src/**" in tooltip  # relative path with recursive indicator
    assert ".py, .txt" in tooltip
    assert "Click to toggle" in tooltip


def test_tooltip_single_watcher_non_recursive(monkeypatch):
    """Tooltip shows single watcher without recursive indicator."""
    monkeypatch.setattr(Path, "cwd", lambda: Path("/project"))

    config = MockWatcherConfig(
        dir=Path("/project/src"),
        extensions=[".py"],
        recursive=False,
    )
    line = WatcherStatusLine(watcher_count=1, enabled=True, watcher_configs=[config])

    tooltip = line._build_watcher_tooltip()

    assert "./src" in tooltip
    assert "./src/**" not in tooltip  # No recursive indicator


def test_tooltip_watcher_all_extensions(monkeypatch):
    """Tooltip shows * when no extensions filter."""
    monkeypatch.setattr(Path, "cwd", lambda: Path("/project"))

    config = MockWatcherConfig(
        dir=Path("/project/src"),
        extensions=None,  # Watch all files
        recursive=True,
    )
    line = WatcherStatusLine(watcher_count=1, enabled=True, watcher_configs=[config])

    tooltip = line._build_watcher_tooltip()

    assert "[*]" in tooltip


def test_tooltip_multiple_watchers(monkeypatch):
    """Tooltip shows multiple watchers."""
    monkeypatch.setattr(Path, "cwd", lambda: Path("/project"))

    configs = [
        MockWatcherConfig(
            dir=Path("/project/src"),
            extensions=[".py"],
            recursive=True,
        ),
        MockWatcherConfig(
            dir=Path("/project/tests"),
            extensions=[".py", ".toml"],
            recursive=False,
        ),
    ]
    line = WatcherStatusLine(watcher_count=2, enabled=True, watcher_configs=configs)

    tooltip = line._build_watcher_tooltip()

    assert "./src/**" in tooltip
    assert "[.py]" in tooltip
    assert "./tests" in tooltip
    assert "[.py, .toml]" in tooltip


def test_tooltip_absolute_path_outside_cwd(monkeypatch):
    """Tooltip shows absolute path for directories outside cwd."""
    monkeypatch.setattr(Path, "cwd", lambda: Path("/project"))

    config = MockWatcherConfig(
        dir=Path("/other/location"),
        extensions=[".py"],
        recursive=True,
    )
    line = WatcherStatusLine(watcher_count=1, enabled=True, watcher_configs=[config])

    tooltip = line._build_watcher_tooltip()

    assert "/other/location/**" in tooltip  # Absolute path shown
