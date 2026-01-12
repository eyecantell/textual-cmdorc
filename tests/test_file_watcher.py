"""Tests for file watcher debouncing and event handling."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from watchdog.events import FileSystemEvent

from cmdorc_frontend.file_watcher import FileWatcherManager, _DebouncedHandler


@pytest.fixture
def mock_orchestrator():
    """Mock CommandOrchestrator."""
    orch = Mock()
    orch.trigger = AsyncMock()
    return orch


@pytest.fixture
def event_loop():
    """Create event loop for testing."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_manager():
    """Mock FileWatcherManager."""
    manager = Mock()
    manager._enabled = True
    return manager


def test_on_any_event_filters_created_and_modified(mock_orchestrator, event_loop, mock_manager):
    """Test that on_any_event only processes created and modified events."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,
        extensions=[".py"],
    )

    # Test created event (should trigger)
    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "created"
    event.src_path = "/test/file.py"

    handler.on_any_event(event)
    assert handler._timer is not None
    handler._timer.cancel()

    # Test modified event (should trigger)
    handler._timer = None
    event.event_type = "modified"
    handler.on_any_event(event)
    assert handler._timer is not None
    handler._timer.cancel()

    # Test deleted event (should NOT trigger)
    handler._timer = None
    event.event_type = "deleted"
    handler.on_any_event(event)
    assert handler._timer is None

    # Test moved event (should NOT trigger)
    event.event_type = "moved"
    handler.on_any_event(event)
    assert handler._timer is None


def test_on_any_event_debounces_multiple_events(mock_orchestrator, event_loop, mock_manager):
    """Test that multiple rapid events only schedule one timer (last one wins)."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=50,
        extensions=[".py"],
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.src_path = "/test/file.py"

    # Simulate rapid created + modified events
    event.event_type = "created"
    handler.on_any_event(event)
    first_timer = handler._timer

    event.event_type = "modified"
    handler.on_any_event(event)
    second_timer = handler._timer

    # Timer should be replaced (different objects)
    # This proves that the second call cancelled the first timer and created a new one
    assert first_timer is not second_timer
    assert second_timer.is_alive()  # Second timer active

    # Clean up
    second_timer.cancel()


def test_on_any_event_skips_directories(mock_orchestrator, event_loop, mock_manager):
    """Test that directory events are ignored."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = True
    event.event_type = "modified"
    event.src_path = "/test/dir"

    handler.on_any_event(event)
    assert handler._timer is None


def test_on_any_event_respects_extension_filter(mock_orchestrator, event_loop, mock_manager):
    """Test that extension filtering works correctly."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,
        extensions=[".py", ".txt"],
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "modified"

    # Should trigger for .py
    event.src_path = "/test/file.py"
    handler.on_any_event(event)
    assert handler._timer is not None
    handler._timer.cancel()

    # Should NOT trigger for .js
    handler._timer = None
    event.src_path = "/test/file.js"
    handler.on_any_event(event)
    assert handler._timer is None


def test_on_any_event_respects_ignore_dirs(mock_orchestrator, event_loop, mock_manager):
    """Test that ignore_dirs filtering works correctly."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,
        extensions=[".py"],
        ignore_dirs=["__pycache__", ".git"],
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "modified"

    # Should trigger for normal path
    event.src_path = "/test/src/file.py"
    handler.on_any_event(event)
    assert handler._timer is not None
    handler._timer.cancel()

    # Should NOT trigger for __pycache__
    handler._timer = None
    event.src_path = "/test/__pycache__/file.py"
    handler.on_any_event(event)
    assert handler._timer is None

    # Should NOT trigger for .git
    handler._timer = None
    event.src_path = "/test/.git/file.py"
    handler.on_any_event(event)
    assert handler._timer is None


def test_cooldown_prevents_double_trigger(mock_orchestrator, event_loop, mock_manager):
    """Test that cooldown period prevents double triggering."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,  # 100ms cooldown
        extensions=[".py"],
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "modified"
    event.src_path = "/test/file.py"

    # Simulate first trigger by manually setting last_trigger_time
    handler._last_trigger_time = time.time()

    # Schedule another trigger immediately (should be blocked by cooldown)
    handler.on_any_event(event)

    # Wait for debounce timer to fire
    if handler._timer:
        handler._timer.join()

    # Orchestrator should NOT have been called (cooldown blocked it)
    mock_orchestrator.trigger.assert_not_called()


def test_cooldown_allows_trigger_after_period(mock_orchestrator, event_loop, mock_manager):
    """Test that triggers work after cooldown period expires."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=50,  # 50ms cooldown
        extensions=[".py"],
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "modified"
    event.src_path = "/test/file.py"

    # Simulate first trigger happened 100ms ago (beyond cooldown)
    handler._last_trigger_time = time.time() - 0.1
    old_time = handler._last_trigger_time

    # Schedule another trigger (should work - outside cooldown)
    handler.on_any_event(event)

    # Wait for debounce timer to fire
    if handler._timer:
        handler._timer.join()

    # The last trigger time SHOULD have been updated (cooldown allowed trigger)
    assert handler._last_trigger_time > old_time


# Tests for last triggered file tracking


def test_manager_initial_no_last_file(mock_orchestrator, event_loop):
    """FileWatcherManager starts with no last triggered file."""
    manager = FileWatcherManager(mock_orchestrator, event_loop)

    file_path, timestamp = manager.get_last_triggered_file()

    assert file_path is None
    assert timestamp is None


def test_manager_set_last_triggered_file(mock_orchestrator, event_loop):
    """_set_last_triggered_file stores file path and timestamp."""
    manager = FileWatcherManager(mock_orchestrator, event_loop)

    test_path = Path("/test/src/app.py")
    test_time = time.time()

    manager._set_last_triggered_file(test_path, test_time)

    file_path, timestamp = manager.get_last_triggered_file()

    assert file_path == test_path
    assert timestamp == test_time


def test_handler_tracks_pending_file(mock_orchestrator, event_loop, mock_manager):
    """Handler tracks the pending file that will trigger."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,
        extensions=[".py"],
    )

    # Initially no pending file
    assert handler._pending_file is None

    # Create a file event
    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "modified"
    event.src_path = "/test/src/app.py"

    handler.on_any_event(event)

    # Pending file should be set
    assert handler._pending_file == Path("/test/src/app.py")

    # Clean up timer
    if handler._timer:
        handler._timer.cancel()


def test_handler_updates_pending_file_on_new_event(mock_orchestrator, event_loop, mock_manager):
    """Handler updates pending file when new events arrive during debounce."""
    handler = _DebouncedHandler(
        trigger_name="test_trigger",
        orchestrator=mock_orchestrator,
        loop=event_loop,
        manager=mock_manager,
        debounce_ms=100,
        extensions=[".py"],
    )

    event = Mock(spec=FileSystemEvent)
    event.is_directory = False
    event.event_type = "modified"

    # First event
    event.src_path = "/test/first.py"
    handler.on_any_event(event)
    assert handler._pending_file == Path("/test/first.py")

    # Second event (should update pending file)
    event.src_path = "/test/second.py"
    handler.on_any_event(event)
    assert handler._pending_file == Path("/test/second.py")

    # Clean up timer
    if handler._timer:
        handler._timer.cancel()
