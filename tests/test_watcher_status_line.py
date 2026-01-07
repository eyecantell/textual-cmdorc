"""Tests for WatcherStatusLine widget."""

from textual_cmdorc.watcher_status_line import WatcherStatusLine


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
