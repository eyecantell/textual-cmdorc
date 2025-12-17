
# Development Plan for textual-cmdorc

## Overview
textual-cmdorc is a Textual-based Terminal User Interface (TUI) that acts as a frontend for the cmdorc library. It loads a TOML configuration file (e.g., config.toml), parses the commands and their lifecycle triggers (specifically "command_success:<name>", "command_failed:<name>", and "command_cancelled:<name>"), and dynamically generates a hierarchical tree of CommandLink widgets (from textual-filelink) using Textual's Tree widget. The hierarchy indents child commands under parents based on these triggers, duplicating commands in the tree if they have multiple parents (treating the structure as a DAG with duplication to form trees).

The TUI will:
- Display commands in an indented hierarchy (e.g., Lint → Format → Tests, with "Another Command" as a root) using Tree for better interactivity and collapsibility.
- Use CommandLink widgets for each command, showing status (e.g., spinner for running, icons for success/failed/cancelled).
- **Show full trigger chain breadcrumbs** in tooltips (e.g., "py_file_changed → command_success:Lint → command_success:Format") extracted from cmdorc's `RunHandle.trigger_chain`.
- **Support global keyboard shortcuts** (1-9 by default) configured in `[keyboard]` section of TOML to play/stop commands from anywhere.
- Update statuses in real-time via cmdorc's lifecycle callbacks.
- Allow manual run/stop via CommandLink's play/stop buttons or keyboard shortcuts.
- Handle automatic triggering, with the output file path set on the CommandLink for viewing results (latest run only).
- Include a log pane for events/output snippets and an input for manual triggers.
- Support file watching via watchdog to trigger events on file changes (e.g., "py_file_changed" on *.py modifications).
- Show helpful hints in tooltips for unconfigured keyboard shortcuts.
- Graceful shutdown on app close.

This plan is for a junior developer: Step-by-step, with code snippets, testing, and rationale. Assume Python/Textual/async basics.

**Estimated Effort:**
- **Original estimate:** 10-14 hours (trigger chains + keyboard shortcuts)
- **With UX enhancements:** +3-4 hours (semantic summaries, validation summary, duplicate indicators, help screen)
- **With embedding architecture:** +3-4 hours (Controller/View/App split for embeddability)
- **Total: 19-24 hours** (Phase 0 is foundational and critical - complete it first)

**Major Architectural Change in v0.1:** The monolithic `CmdorcApp` design is replaced with a three-layer embeddable architecture to support both standalone TUI and embedding in larger applications. See Phase 0 for details.

### Prerequisites
- Python 3.10+.
- Install: `pdm install` or `pip install textual textual-filelink cmdorc watchdog`.
- Read:
  - cmdorc: README.md and architecture.md. **NEW:** Understand `RunHandle.trigger_chain` property for breadcrumb display and `TriggerContext` for trigger tracking.
  - textual-filelink: README.md (focus on CommandLink API: constructor, set_status, set_output_path, events like PlayClicked). **NEW:** Understand `action_play_stop()` method and BINDINGS customization for keyboard support.
  - Textual docs: https://textual.textualize.io/ (widgets: Tree, Log, Input; events; on_key() handler for global keyboard; workers for async).
  - Watchdog docs: https://python-watchdog.readthedocs.io/ (focus on PollingObserver for cross-platform).

### Project Structure
```
textual-cmdorc/
├── src/
│   ├── cmdorc_frontend/           # NEW: Shared
│   │   ├── __init__.py
│   │   ├── config.py              # Config parsing + hierarchy
│   │   ├── models.py              # Shared data models
│   │   ├── state_manager.py       # State reconciliation logic
│   │   └── watchers.py            # Abstract watcher interface
│   │
│   └── textual_cmdorc/            # TUI implementation
│       ├── __init__.py
│       ├── app.py
│       ├── widgets.py
│       ├── integrator.py          # TUI-specific wiring
│       └── file_watcher.py        # Concrete watchdog impl
├── examples/
│   └── config.toml             # Query example
├── pyproject.toml              # Dependencies: textual, textual-filelink, cmdorc, watchdog
├── README.md                   # Usage
├── LICENSE                     # MIT
└── tests/
    ├── test_config.py         # Config tests
    ├── test_file_watcher.py   # Watcher tests
    ├── test_integrator.py     # Widget wiring tests
    ├── test_widgets.py        # CmdorcCommandLink tests
    └── test_app.py            # TUI integration tests
```

pyproject.toml excerpt:
```toml
[project]
name = "textual-cmdorc"
version = "0.1.0"
dependencies = ["textual>=0.47.0", "textual-filelink>=0.2.0", "cmdorc>=0.1.0", "watchdog>=4.0.0"]

[tool.pdm.dev-dependencies]
test = ["pytest", "pytest-asyncio", "pytest-cov"]

[tool.pytest.ini_options]
addopts = "--cov=src/textual_cmdorc --cov-report=term-missing --cov-fail-under=90"
```

## Configuration Format with New Features

### TOML Schema

```toml
# Keyboard shortcuts (NEW) - optional section
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3", Build = "b" }
enabled = true                    # optional, default true
show_in_tooltips = true           # optional, default true

# File watchers - optional, may appear multiple times
[[file_watcher]]
dir = "./src"
patterns = ["**/*.py"]
trigger = "py_file_changed"
debounce_ms = 300

# Commands - standard cmdorc format
[[command]]
name = "Lint"
command = "ruff check --fix"
triggers = ["py_file_changed"]
```

### Key Points:
- `[keyboard]` section is optional. If missing, no keyboard shortcuts are configured (but app still works).
- `shortcuts` is a dict mapping command names to keys (digits, letters, f-keys).
- Duplicate keys will log warnings; last definition wins.
- References to unknown commands will log warnings.

## Implementation Phases Overview

This implementation is organized into **8 phases** (up from the original 10-step structure):

- **Phase 0** (3-4 hours): Embeddable architecture - Create Controller, View, and Notifier to support both standalone and embedded usage modes
- **Phases 1-7** (16-20 hours): Features, UX, and polish - Config parsing, trigger chains, duplicate indicators, keyboard shortcuts, validation, help screen, and integration

**Total Estimated Effort:** 19-24 hours (up from 10-14 hours originally, due to embedding architecture + UX enhancements)

**Key Architectural Change:** The monolithic `CmdorcApp` is now split into three layers:
1. **CmdorcController** (Layer 3) - Non-Textual, handles orchestration
2. **CmdorcView** (Layer 2) - Passive Textual widget, handles rendering
3. **CmdorcApp** (Layer 1) - Thin shell for standalone mode

This enables both standalone TUI and embedding in larger applications.

---

## Phase 0: Embeddable Architecture (FOUNDATIONAL - 6-8 HOURS)

This phase establishes the foundational architecture that enables the project to work both standalone and embedded. **Complete this phase before starting other features.**

**Critical Fixes Integrated:**
- FIX #1: Sync-safe async API (store `_loop`, use `self._loop.create_task()`)
- FIX #2: Duplicate tracking in view (`_command_links` as dict[str, list[...]])
- FIX #3: Keyboard conflicts cached property (computed once in `__init__()`)
- FIX #5: Watcher threading safety with `call_soon_threadsafe()`
- FIX #6: Help screen as ModalScreen with `h` footer binding
- RECOMMENDATION #1: Idempotent `attach()` with loop validation
- RECOMMENDATION #2: Stable public API explicitly documented
- RECOMMENDATION #3: Centralized validation results in controller
- POLISH #1: `keyboard_hints` metadata-only (not bindings)
- POLISH #3: Default notifier is NoOpNotifier (silent for embedded mode)

### Phase 0, Step 1: Create CmdorcNotifier Protocol & Implementations (30 min)

**Why:** Pluggable logging allows host apps to control notification behavior.

Create `src/cmdorc_frontend/notifier.py`:

```python
# src/cmdorc_frontend/notifier.py
from typing import Protocol
import logging
from textual.widgets import Log

class CmdorcNotifier(Protocol):
    """Protocol for pluggable notifications."""

    def info(self, message: str) -> None:
        """Informational message."""
        ...

    def warning(self, message: str) -> None:
        """Warning message."""
        ...

    def error(self, message: str) -> None:
        """Error message."""
        ...


class LoggingNotifier:
    """Default implementation using stdlib logging."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

    def info(self, msg: str) -> None:
        self.logger.info(msg)

    def warning(self, msg: str) -> None:
        self.logger.warning(msg)

    def error(self, msg: str) -> None:
        self.logger.error(msg)


class TextualLogPaneNotifier:
    """Textual-specific implementation for standalone mode."""

    def __init__(self, log_pane: Log):
        self.log_pane = log_pane

    def info(self, msg: str) -> None:
        self.log_pane.write_line(f"ℹ️  {msg}")

    def warning(self, msg: str) -> None:
        self.log_pane.write_line(f"⚠️  {msg}")

    def error(self, msg: str) -> None:
        self.log_pane.write_line(f"❌ {msg}")
```

### Phase 0, Step 2: Create CmdorcController Class (1.5 hours)

**Why:** Non-Textual controller enables programmatic use without Textual dependency.

Create `src/textual_cmdorc/controller.py`:

```python
# src/textual_cmdorc/controller.py
import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional
from cmdorc import CommandOrchestrator
from cmdorc_frontend.config import load_frontend_config
from cmdorc_frontend.models import TriggerSource, CommandNode
from cmdorc_frontend.notifier import CmdorcNotifier, NoOpNotifier
from textual_cmdorc.file_watcher import WatchdogWatcher

logger = logging.getLogger(__name__)


class CmdorcController:
    """Non-Textual controller for orchestration logic. Primary embed point.

    RECOMMENDATION #2: Stable Public API for v0.1
    ============================================
    Stable methods: attach(), detach(), request_run(), request_cancel(),
    run_command(), cancel_command(), keyboard_hints, keyboard_conflicts.
    Internal methods (_on_file_change, etc.) may change.
    """

    def __init__(
        self,
        config_path: str | Path,
        notifier: CmdorcNotifier | None = None,
        enable_watchers: bool = True
    ):
        """Initialize controller.

        Args:
            config_path: Path to TOML config
            notifier: Optional notification handler (defaults to NoOpNotifier - silent)
            enable_watchers: If True, watchers auto-start on attach(). If False, host controls lifecycle.
        """
        self.config_path = Path(config_path)
        self.notifier = notifier or NoOpNotifier()  # POLISH #3: Silent by default
        self.enable_watchers = enable_watchers
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # FIX #1: Store loop reference
        self._file_watcher: Optional[WatchdogWatcher] = None

        # Load configuration
        (
            self.runner_config,
            self.keyboard_config,
            self.watcher_configs,
            self.hierarchy
        ) = load_frontend_config(self.config_path)

        # Initialize orchestrator
        self.orchestrator = CommandOrchestrator(self.runner_config)

        # FIX #3: Cache keyboard conflicts (computed once)
        self._keyboard_conflicts = self._compute_keyboard_conflicts()

        # Outbound events (host wires these)
        self.on_command_started: Callable[[str, TriggerSource], None] | None = None
        self.on_command_finished: Callable[[str, object], None] | None = None
        self.on_validation_result: Callable[[dict], None] | None = None
        self.on_state_reconciled: Callable[[str, object], None] | None = None  # FIX #6

        # Intent signals
        self.on_quit_requested: Callable[[], None] | None = None
        self.on_cancel_all_requested: Callable[[], None] | None = None

    def _compute_keyboard_conflicts(self) -> dict[str, list[str]]:
        """FIX #3: Compute keyboard conflicts once during init."""
        conflicts = {}
        for cmd_name, key in self.keyboard_config.shortcuts.items():
            if key not in conflicts:
                conflicts[key] = []
            conflicts[key].append(cmd_name)
        # Return only keys with multiple commands
        return {k: v for k, v in conflicts.items() if len(v) > 1}

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach to event loop and start watchers if enabled.

        RECOMMENDATION #1: Idempotent - guards against double-attach and non-running loop.
        FIX #1: Store loop reference for sync-safe task creation.
        """
        # RECOMMENDATION #1: Idempotency guard
        if self._loop is not None:
            return  # Already attached

        # RECOMMENDATION #1: Validate loop is running
        if not loop.is_running():
            raise RuntimeError("Event loop must be running before attach(). "
                             "Call attach() from within on_mount() or after loop started.")

        self._loop = loop  # FIX #1: Store for request_run/cancel

        if self.enable_watchers and self.watcher_configs:
            self._file_watcher = WatchdogWatcher(self.orchestrator, loop)
            for cfg in self.watcher_configs:
                self._file_watcher.add_watch(cfg)
            self._file_watcher.start()
            self.notifier.info(f"File watchers started ({len(self.watcher_configs)} configured)")

    def detach(self) -> None:
        """Stop watchers and cleanup."""
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None
        self._loop = None
        self.notifier.info("File watchers stopped")

    async def run_command(self, name: str) -> None:
        """Run a command by name (async)."""
        if not self.orchestrator.has_command(name):
            self.notifier.warning(f"Command not found: {name}")
            return
        await self.orchestrator.run_command(name)
        self.notifier.info(f"Started: {name}")

    async def cancel_command(self, name: str) -> None:
        """Cancel a running command (async)."""
        if not self.orchestrator.has_command(name):
            self.notifier.warning(f"Command not found: {name}")
            return
        await self.orchestrator.cancel_command(name)
        self.notifier.info(f"Cancelled: {name}")

    async def reload_config(self) -> None:
        """Reload configuration from disk."""
        try:
            (
                self.runner_config,
                self.keyboard_config,
                self.watcher_configs,
                self.hierarchy
            ) = load_frontend_config(self.config_path)
            # FIX #3: Recompute conflicts after reload
            self._keyboard_conflicts = self._compute_keyboard_conflicts()
            self.notifier.info("Configuration reloaded")
        except Exception as e:
            self.notifier.error(f"Failed to reload config: {e}")

    # FIX #1: Sync-safe helpers for UI integration
    def request_run(self, name: str) -> None:
        """Request command run (sync-safe, schedules async task).

        FIX #1: Uses stored loop reference instead of asyncio.create_task().
        Safe to call from sync contexts (e.g., keyboard event handlers).
        """
        if self._loop is None:
            raise RuntimeError("Controller not attached to event loop. Call attach() first.")
        self._loop.create_task(self.run_command(name))

    def request_cancel(self, name: str) -> None:
        """Request command cancellation (sync-safe, schedules async task).

        FIX #1: Uses stored loop reference instead of asyncio.create_task().
        Safe to call from sync contexts (e.g., keyboard event handlers).
        """
        if self._loop is None:
            raise RuntimeError("Controller not attached to event loop. Call attach() first.")
        self._loop.create_task(self.cancel_command(name))

    # FIX #5: Thread-safe file change handler
    def _on_file_change(self, trigger_name: str) -> None:
        """Handle file change events from watcher thread.

        FIX #5: Uses call_soon_threadsafe to schedule async task from watcher thread.
        """
        if self._loop is None:
            logger.warning(f"File change for '{trigger_name}' ignored - controller not attached")
            return
        # FIX #5: Thread-safe task scheduling
        self._loop.call_soon_threadsafe(
            lambda: self._loop.create_task(self.run_command(trigger_name))
        )

    # POLISH #1: Metadata only (no callables)
    @property
    def keyboard_hints(self) -> dict[str, str]:
        """Returns {key: command_name} metadata for host to wire.

        POLISH #1: Returns metadata only (no callables) to decouple host from controller internals.
        Host wires own actions: self.bind(key, lambda: controller.request_run(name))
        """
        return {
            key: cmd_name
            for cmd_name, key in self.keyboard_config.shortcuts.items()
        }

    # FIX #3: Cached keyboard conflicts
    @property
    def keyboard_conflicts(self) -> dict[str, list[str]]:
        """FIX #3: Returns {key: [cmd_name1, cmd_name2, ...]} for keys with multiple commands.

        Cached in __init__() to avoid recomputation on every access.
        """
        return self._keyboard_conflicts
```

### Phase 0, Step 3: Create CmdorcView Widget (1 hour)

**Why:** Passive Textual widget for rendering that works in embedded contexts.

Create `src/textual_cmdorc/view.py`:

```python
# src/textual_cmdorc/view.py
from textual.widget import Widget
from textual.widgets import Tree
from textual.containers import Container
from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.widgets import CmdorcCommandLink


class CmdorcView(Widget):
    """Textual widget for rendering cmdorc command tree. Suitable for embedding."""

    def __init__(
        self,
        controller: CmdorcController,
        show_log_pane: bool = True,
        enable_local_bindings: bool = False
    ):
        """Initialize view.

        Args:
            controller: CmdorcController instance
            show_log_pane: Whether to render log pane
            enable_local_bindings: If True, handle keys when focused (standalone only)
        """
        super().__init__()
        self.controller = controller
        self.show_log_pane = show_log_pane
        self.enable_local_bindings = enable_local_bindings
        # FIX #2: Track all instances of each command to detect duplicates
        self._command_links: dict[str, list[CmdorcCommandLink]] = {}

    def compose(self):
        """Compose tree and optional log pane."""
        tree = Tree("Commands")
        yield tree

        # Optional log pane
        if self.show_log_pane:
            from textual.widgets import Log
            yield Log()

    def on_mount(self) -> None:
        """Build command tree from controller.hierarchy."""
        tree = self.query_one(Tree)
        self._build_tree(tree, self.controller.hierarchy)

    def _build_tree(self, tree, nodes, parent=None):
        """Recursively build tree from CommandNode hierarchy.

        FIX #2: Tracks command occurrences to detect duplicates and mark them.
        """
        from textual_cmdorc.integrator import create_command_link

        for node in nodes:
            # Get keyboard shortcut for this command
            shortcut = (self.controller.keyboard_config.shortcuts.get(node.name)
                       if self.controller.keyboard_config.enabled else None)

            # FIX #2: Detect if this is a duplicate (appeared before)
            occurrence_count = len(self._command_links.get(node.name, []))
            is_duplicate = occurrence_count > 0

            # Create link with shortcut and duplicate indicator
            link = create_command_link(node, self.controller.orchestrator,
                                      keyboard_shortcut=shortcut)
            link.is_duplicate = is_duplicate  # FIX #2: Mark duplicates

            # FIX #2: Store all instances of this command
            if node.name not in self._command_links:
                self._command_links[node.name] = []
            self._command_links[node.name].append(link)

            # Refresh tooltips to reflect duplicate status
            link._update_tooltips()

            # Add to tree
            if parent is None:
                tree.root.add(link)
            else:
                parent.add(link)

            # Recursively add children
            if node.children:
                self._build_tree(tree, node.children, link)

    def refresh_tree(self) -> None:
        """Rebuild tree from controller.hierarchy."""
        tree = self.query_one(Tree)
        tree.clear()
        self._command_links.clear()
        self._build_tree(tree, self.controller.hierarchy)
```

### Phase 0, Step 4: Refactor CmdorcApp to Thin Shell (1 hour)

**Why:** CmdorcApp becomes a lightweight standalone wrapper, not the monolith.

Update `src/textual_cmdorc/app.py`:

```python
# src/textual_cmdorc/app.py
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Container
from textual_cmdorc.controller import CmdorcController
from textual_cmdorc.view import CmdorcView


class CmdorcApp(App):
    """Standalone mode - thin shell composing controller + view."""

    TITLE = "cmdorc TUI"
    SUB_TITLE = "Command orchestration interface"

    def __init__(self, config_path: str = "config.toml", **kwargs):
        super().__init__(**kwargs)
        self.controller = CmdorcController(config_path, enable_watchers=True)
        self.view: CmdorcView | None = None

    def compose(self) -> ComposeResult:
        """Compose app with header, view, footer."""
        yield Header()
        self.view = CmdorcView(self.controller, show_log_pane=True)
        yield self.view
        yield Footer()

    async def on_mount(self) -> None:
        """Attach controller to event loop and bind keyboard shortcuts."""
        loop = asyncio.get_running_loop()
        self.controller.attach(loop)

        # Bind global keyboard shortcuts
        for key, (cmd_name, callback) in self.controller.keyboard_bindings.items():
            self.bind(key, f"run_command('{cmd_name}')", description=f"Run/stop {cmd_name}")

    async def on_unmount(self) -> None:
        """Cleanup on shutdown."""
        self.controller.detach()

    async def action_quit(self) -> None:
        """Quit application."""
        self.exit()

    async def action_reload_config(self) -> None:
        """Reload configuration."""
        await self.controller.reload_config()
        if self.view:
            self.view.refresh_tree()
```

### Phase 0, Step 5: Write Integration Tests (1 hour)

**Why:** Verify controller/view architecture works before building features.

Create `tests/test_controller.py`:

```python
# tests/test_controller.py
import pytest
import asyncio
from pathlib import Path
from textual_cmdorc.controller import CmdorcController
from cmdorc_frontend.notifier import LoggingNotifier


@pytest.mark.asyncio
async def test_controller_initialization(tmp_path):
    """Test controller loads config and initializes."""
    config = tmp_path / "config.toml"
    config.write_text("""
[[command]]
name = "Test"
command = "echo test"
triggers = []
""")

    controller = CmdorcController(config)
    assert controller is not None
    assert len(controller.hierarchy) >= 1


@pytest.mark.asyncio
async def test_controller_attach_detach(tmp_path):
    """Test controller lifecycle."""
    config = tmp_path / "config.toml"
    config.write_text("""
[[command]]
name = "Test"
command = "echo test"
triggers = []
""")

    controller = CmdorcController(config, enable_watchers=False)
    loop = asyncio.get_running_loop()

    controller.attach(loop)  # Should not raise
    controller.detach()  # Should not raise


@pytest.mark.asyncio
async def test_keyboard_bindings(tmp_path):
    """Test keyboard metadata exposure."""
    config = tmp_path / "config.toml"
    config.write_text("""
[keyboard]
shortcuts = { Test = "1" }

[[command]]
name = "Test"
command = "echo test"
triggers = []
""")

    controller = CmdorcController(config)
    bindings = controller.keyboard_bindings
    assert "1" in bindings
    assert bindings["1"][0] == "Test"
```

**Summary of Phase 0 (COMPLETE - 6-8 HOURS):**

After this phase, you have:
- ✅ Non-Textual controller that can be used programmatically
- ✅ Passive view widget suitable for embedding
- ✅ Standalone app that composes them for TUI mode
- ✅ Pluggable notifier for custom logging (POLISH #3: silent by default)
- ✅ Full architecture enabling both embedded and standalone usage

**All Critical Fixes Applied:**
- ✅ **FIX #1**: Sync-safe intent methods (`request_run`, `request_cancel`) using stored `_loop`
- ✅ **FIX #2**: Duplicate tracking in view using `dict[str, list[CmdorcCommandLink]]`
- ✅ **FIX #3**: Keyboard conflicts cached property computed once in `__init__()`
- ✅ **FIX #5**: Watcher threading safety using `call_soon_threadsafe()`
- ✅ **FIX #6**: Help screen with ModalScreen and `h` footer binding (Phase 6)
- ✅ **RECOMMENDATION #1**: Idempotent `attach()` with loop validation
- ✅ **RECOMMENDATION #2**: Stable public API documented in controller docstring
- ✅ **RECOMMENDATION #3**: Validation centralized in controller
- ✅ **POLISH #1**: `keyboard_hints` metadata-only (not bindings)
- ✅ **POLISH #3**: Default notifier is NoOpNotifier (silent)

**Anti-Patterns to Avoid (FIX #7 - Design Principles):**
- ❌ Do not bind global keys inside the controller
- ❌ Do not call `exit()` or `app.exit()` from controller
- ❌ Do not poll orchestrator state (use callbacks only)
- ❌ Do not make controller depend on Textual
- ❌ Do not auto-start watchers without checking `enable_watchers`

You're now ready for Phases 1-7, which add features while maintaining this embedding-first architecture.

---

## Phase 1: Configuration & Model Enhancement (2-3 hours)

**Critical Fixes in Phase 1:**
- **FIX #4**: TriggerSource adapter pattern (keeps models UI-agnostic)
- **FIX #7**: Tooltip truncation min width check (10 chars)
- **FIX #8**: Key validation against VALID_KEYS set

### Phase 1, Step 1: Project Setup & Boilerplate (1-2 hours)
- Create structure as above.
- In `textual_cmdorc/__init__.py`: `from .app import CmdorcApp`
- In `cmdorc_frontend/models.py`: Shared models.
```python
# src/cmdorc_frontend/models.py
from dataclasses import dataclass
from typing import Literal
from pathlib import Path
from cmdorc import RunState, CommandConfig

@dataclass
class TriggerSource:
    name: str  # Last trigger in chain (backward compat)
    kind: Literal["manual", "file", "lifecycle"]
    chain: list[str] = field(default_factory=list)  # NEW: Full trigger chain from cmdorc

    @classmethod
    def from_trigger_chain(cls, trigger_chain: list[str]) -> 'TriggerSource':
        """Create from cmdorc's RunHandle.trigger_chain."""
        if not trigger_chain:
            return cls(name="manual", kind="manual", chain=[])
        last_trigger = trigger_chain[-1]
        kind = ("lifecycle" if last_trigger.startswith("command_")
                else "file" if "file" in last_trigger.lower()
                else "manual")
        return cls(name=last_trigger, kind=kind, chain=trigger_chain)

    def format_chain(self, separator: str = " → ", max_width: int | None = None) -> str:
        """Format chain for display, with optional left truncation."""
        if not self.chain:
            return "manual"
        full_chain = separator.join(self.chain)
        if max_width and len(full_chain) > max_width:
            keep_chars = max_width - 4
            if keep_chars > 0:
                return f"...{separator}{full_chain[-keep_chars:]}"
        return full_chain

@dataclass
class KeyboardConfig:  # NEW
    shortcuts: dict[str, str]  # command_name -> key
    enabled: bool = True
    show_in_tooltips: bool = True

@dataclass
class PresentationUpdate:
    icon: str
    running: bool
    tooltip: str
    output_path: Path | None = None

@dataclass
class CommandNode:
    config: CommandConfig  # ✅ Store full config
    children: list['CommandNode'] = None  # type: ignore

    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def triggers(self) -> list[str]:
        return self.config.triggers

def map_run_state_to_icon(state: RunState) -> str:
    """Map cmdorc.RunState enum to UI icons."""
    if state == RunState.SUCCESS:
        return "✅"
    elif state == RunState.FAILED:
        return "❌"
    elif state == RunState.CANCELLED:
        return "⏹"
    elif state == RunState.RUNNING:
        return "⏳"
    else:
        return "⏸"  # PENDING
```
- In `textual_cmdorc/utils.py`: TUI-specific utils.
```python
# src/textual_cmdorc/utils.py
import logging

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
```
- Test: `pdm run python -m textual_cmdorc` (expect error if incomplete). Run `pdm run ruff check .` for linting.

Rationale: Sets up PDM, shared models for reuse.

### Step 2: Shared Config Parsing (4-6 hours)
- In `cmdorc_frontend/config.py`: Load TOML, build hierarchy, parse keyboard config, parse watchers.
```python
# src/cmdorc_frontend/config.py
from typing import Dict, List, Tuple
from pathlib import Path
import re
import tomllib  # or tomli for <3.11
import logging
from cmdorc import load_config as load_cmdorc_config, RunnerConfig, CommandConfig
from .models import CommandNode, KeyboardConfig
from .watchers import WatcherConfig

def load_frontend_config(path: str | Path) -> Tuple[RunnerConfig, KeyboardConfig, List[WatcherConfig], List[CommandNode]]:
    """Load configuration for any frontend."""
    path = Path(path)
    raw = tomllib.loads(path.read_text())

    # NEW: Parse keyboard config
    keyboard_raw = raw.get("keyboard", {})
    keyboard_config = KeyboardConfig(
        shortcuts=keyboard_raw.get("shortcuts", {}),
        enabled=keyboard_raw.get("enabled", True),
        show_in_tooltips=keyboard_raw.get("show_in_tooltips", True),
    )

    # NEW: Validate keyboard config
    key_to_commands = {}
    for cmd_name, key in keyboard_config.shortcuts.items():
        if key in key_to_commands:
            logging.warning(f"Duplicate keyboard shortcut '{key}' for commands '{cmd_name}' and '{key_to_commands[key]}' - last one wins")
        key_to_commands[key] = cmd_name

    # Parse watchers
    watchers = [
        WatcherConfig(
            dir=path.parent / Path(w["dir"]),
            patterns=w.get("patterns"),
            extensions=w.get("extensions"),
            ignore_dirs=w.get("ignore_dirs", ["__pycache__", ".git"]),
            trigger=w["trigger"],
            debounce_ms=w.get("debounce_ms", 300),
        )
        for w in raw.get("file_watcher", [])
    ]

    # Use cmdorc's loader
    runner_config = load_cmdorc_config(path)

    # NEW: Validate that shortcuts reference real commands
    command_names = {c.name for c in runner_config.commands}
    for cmd_name in keyboard_config.shortcuts:
        if cmd_name not in command_names:
            logging.warning(f"Keyboard shortcut defined for unknown command '{cmd_name}'")
    
    # Build hierarchy
    commands: Dict[str, CommandConfig] = {c.name: c for c in runner_config.commands}
    graph: Dict[str, List[str]] = {name: [] for name in commands}
    
    for name, config in commands.items():
        for trigger in config.triggers:
            match = re.match(r"(command_success|command_failed|command_cancelled):(.+)", trigger)
            if match:
                trigger_type, parent = match.groups()
                if parent in graph:
                    graph[parent].append(name)
                else:
                    logging.warning(f"Unknown parent '{parent}' for {name}")
    
    visited: set[str] = set()
    roots: List[CommandNode] = []
    
    def build_node(name: str, visited_local: set[str]) -> CommandNode | None:
        if name in visited_local:
            logging.warning(f"Cycle detected at {name}, skipping duplicate")
            return None
        visited_local.add(name)
        node = CommandNode(config=commands[name])  # ✅ Pass full config
        for child_name in graph.get(name, []):
            child_node = build_node(child_name, visited_local.copy())
            if child_node:
                node.children.append(child_node)
        return node
    
    all_children = {c for children in graph.values() for c in children}
    potential_roots = [name for name in commands if name not in all_children]
    
    for root_name in potential_roots:
        if root_name not in visited:
            root_node = build_node(root_name, set())
            if root_node:
                roots.append(root_node)
                visited.add(root_name)
    
    return runner_config, keyboard_config, watchers, roots

def init_keyboard_config(runner_config: RunnerConfig, output_path: Path | None = None) -> str:
    """NEW: Generate initial [keyboard] section with no-op placeholders."""
    shortcuts = {cmd.name: f"<key{i+1}>" for i, cmd in enumerate(runner_config.commands)}
    toml_content = "[keyboard]\n"
    toml_content += "shortcuts = {\n"
    for name, key in shortcuts.items():
        toml_content += f'    "{name}" = "{key}",\n'
    toml_content += "}\nenabled = true\n"
    if output_path:
        output_path.write_text(toml_content)
    return toml_content
```
- Test: `test_config.py` – Use example config.toml, assert hierarchy, watchers, keyboard config parsing. Test init_keyboard_config() generation.

Rationale: Shared config logic for any frontend. NEW: Keyboard config parsing + init helper for user convenience.

### Step 3: Shared State Manager (2-3 hours)
- In `cmdorc_frontend/state_manager.py`: Reconciliation logic.
```python
# src/cmdorc_frontend/state_manager.py
from typing import Protocol
from pathlib import Path
from cmdorc import CommandOrchestrator, RunResult, RunState
from .models import TriggerSource, PresentationUpdate

class CommandView(Protocol):
    """Abstract interface any frontend must implement."""
    def set_running(self, running: bool, tooltip: str) -> None: ...
    def set_result(self, icon: str, tooltip: str, output_path: Path | None) -> None: ...
    @property
    def command_name(self) -> str: ...

class StateReconciler:
    def __init__(self, orchestrator: CommandOrchestrator):
        self.orchestrator = orchestrator
    
    def reconcile(self, view: CommandView) -> None:
        """Sync view state with cmdorc state - UI-agnostic."""
        active = self.orchestrator.get_active_handles(view.command_name)
        
        if active:
            handle = active[-1]
            if handle.is_finalized:
                # Update with result
                view.set_result(
                    icon=self._map_state_icon(handle.state),
                    tooltip=f"{handle.state.value} ({handle.duration_str})",
                    output_path=handle._result.output if handle._result else None
                )
            else:
                view.set_running(True, f"Running: {handle.comment or 'Running'}")
        else:
            # Check history
            history = self.orchestrator.get_history(view.command_name, limit=1)
            if history:
                result = history[0]
                view.set_result(
                    icon=self._map_state_icon(result.state),
                    tooltip=f"{result.state.value} ({result.duration_str})",
                    output_path=result.output
                )

    def _map_state_icon(self, state: RunState) -> str:
        if state == RunState.SUCCESS: return "✅"
        if state == RunState.FAILED: return "❌"
        if state == RunState.CANCELLED: return "⏹"
        return "❓"
```
- Test: Mock view/orchestrator, assert set methods called.

Rationale: UI-agnostic reconciliation.

### Step 4: Shared Watcher Interface (1-2 hours)
- In `cmdorc_frontend/watchers.py`: Abstract protocol.
```python
# src/cmdorc_frontend/watchers.py
from typing import Protocol
from dataclasses import dataclass
from pathlib import Path

@dataclass
class WatcherConfig:
    dir: Path
    patterns: list[str] | None = None
    extensions: list[str] | None = None
    ignore_dirs: list[str] | None = None
    trigger: str = ""
    debounce_ms: int = 300

class TriggerSourceWatcher(Protocol):
    def add_watch(self, config: WatcherConfig) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
```
- Test: N/A (protocol).

Rationale: Allows frontend-specific watchers.

### Step 6: TUI-Specific File Watcher (2-3 hours)
- In `textual_cmdorc/file_watcher.py`: Concrete watchdog impl implementing protocol.
```python
# src/textual_cmdorc/file_watcher.py
from cmdorc_frontend.watchers import TriggerSourceWatcher, WatcherConfig
from dataclasses import dataclass
from pathlib import Path
from typing import List
import asyncio
import logging
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers.polling import PollingObserver as Observer
from cmdorc import CommandOrchestrator

logger = logging.getLogger(__name__)

class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, trigger: str, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop, debounce_ms: int = 300):
        self.trigger = trigger
        self.orchestrator = orchestrator
        self.loop = loop
        self.debounce_ms = debounce_ms
        self._tasks: dict[str, asyncio.Task] = {}

    def _schedule(self, event: FileSystemEvent):
        # Use trigger name as key - debounces across all files for this watcher
        # E.g., changing 3 .py files rapidly → only one "py_file_changed" trigger
        key = self.trigger
        if key in self._tasks:
            self._tasks[key].cancel()
        self._tasks[key] = asyncio.create_task(self._delayed_trigger())

    async def _delayed_trigger(self):
        await asyncio.sleep(self.debounce_ms / 1000.0)
        try:
            await self.orchestrator.trigger(self.trigger)
            logger.info(f"File change → triggered '{self.trigger}'")
        except Exception as e:
            logger.error(f"Failed to trigger '{self.trigger}': {e}")

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if not self.loop.is_running():
            logger.error("Event loop stopped, cannot schedule file event")
            return
        self.loop.call_soon_threadsafe(lambda: self._schedule(event))

class WatchdogWatcher(TriggerSourceWatcher):
    def __init__(self, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop):
        self.orchestrator = orchestrator
        self.loop = loop
        self.observer = Observer()
        self.handlers: List[_DebouncedHandler] = []

    def add_watch(self, config: WatcherConfig) -> None:
        if not config.dir.exists():
            logger.warning(f"Watcher directory does not exist: {config.dir}")
            return
        handler = _DebouncedHandler(config.trigger, self.orchestrator, self.loop, config.debounce_ms)
        self.observer.schedule(handler, str(config.dir.resolve()), recursive=True)
        self.handlers.append(handler)
        logger.info(f"Started watcher on {config.dir} → '{config.trigger}'")

    def start(self) -> None:
        self.observer.start()
        logger.info("File watcher manager started")

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join(timeout=2.0)
        for task in [t for h in self.handlers for t in h._tasks.values()]:
            task.cancel()
        logger.info("File watcher manager stopped")
```
- Test: `test_file_watcher.py` – Mock observer/loop, simulate events, assert trigger called after debounce.

Rationale: Concrete impl for TUI; follows shared protocol.

### Step 6: TUI Widgets (2-3 hours)
- In `textual_cmdorc/widgets.py`: CmdorcCommandLink implementing CommandView with trigger chain display.
```python
# src/textual_cmdorc/widgets.py
from textual_filelink import CommandLink
from cmdorc import CommandConfig, RunResult, RunState
from cmdorc_frontend.state_manager import CommandView
from cmdorc_frontend.models import TriggerSource, PresentationUpdate, map_run_state_to_icon

class CmdorcCommandLink(CommandLink, CommandView):
    def __init__(self, config: CommandConfig, keyboard_shortcut: str | None = None, **kwargs):
        super().__init__(
            label=config.name,
            output_path=None,
            initial_status_icon="❓",
            initial_status_tooltip="Idle",
            show_toggle=False,
            show_settings=False,
            show_remove=False,
            **kwargs
        )
        self.config = config
        self.current_trigger: TriggerSource = TriggerSource("Idle", "manual", chain=[])
        self.keyboard_shortcut = keyboard_shortcut  # NEW
        self._update_tooltips()

    @property
    def command_name(self) -> str:
        return self.config.name

    def set_running(self, running: bool, tooltip: str) -> None:
        self.set_status(running=running, tooltip=tooltip)

    def set_result(self, icon: str, tooltip: str, output_path: Path | None) -> None:
        self.set_status(icon=icon, running=False, tooltip=tooltip)
        if output_path:
            self.set_output_path(output_path)

    def apply_update(self, update: PresentationUpdate) -> None:
        self.set_status(icon=update.icon, running=update.running, tooltip=update.tooltip)
        if update.output_path:
            self.set_output_path(update.output_path)

    def update_from_run_result(self, result: RunResult, trigger_source: TriggerSource) -> None:
        icon = map_run_state_to_icon(result.state)
        chain_display = trigger_source.format_chain()  # NEW: Show full chain
        tooltip = f"{result.state.value} ({result.duration_str})\nTrigger chain: {chain_display}"
        update = PresentationUpdate(icon=icon, running=(result.state == RunState.RUNNING), tooltip=tooltip, output_path=result.output if result.state in [RunState.SUCCESS, RunState.FAILED, RunState.CANCELLED] else None)
        self.apply_update(update)
        self.current_trigger = trigger_source
        self._update_tooltips()

    def _update_tooltips(self) -> None:
        if self.is_running:
            chain_display = self.current_trigger.format_chain()  # NEW
            tooltip = f"Stop — Trigger chain: {chain_display}"
            if self.keyboard_shortcut:  # NEW
                tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to stop"
            self.set_stop_tooltip(tooltip)
        else:
            triggers = ", ".join(self.config.triggers) or "none"
            tooltip = f"Run (Triggers: {triggers} | manual)"
            if self.keyboard_shortcut:  # NEW
                tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to run"
            else:
                # NEW: Show hint for unconfigured shortcuts
                tooltip = f"{tooltip}\nSet hotkey with {self.config.name} = '<key>' in [keyboard] shortcuts"
            self.set_play_tooltip(tooltip)
```
- Test: `test_widgets.py` – Create link, call update_from_run_result with trigger chain, assert tooltips show chain and shortcuts.

Rationale: NEW: Adds trigger chain display and keyboard shortcut hints; handles output path.

### Step 7: TUI Integrator (2-3 hours)
- In `textual_cmdorc/integrator.py`: TUI-specific wiring with trigger chain extraction.
```python
# src/textual_cmdorc/integrator.py
from typing import Callable
from cmdorc import CommandOrchestrator, RunHandle, RunResult, RunState
from cmdorc_frontend.state_manager import StateReconciler
from cmdorc_frontend.models import TriggerSource, PresentationUpdate
from .widgets import CmdorcCommandLink
from cmdorc_frontend.config import CommandNode
import logging

def create_command_link(
    node: CommandNode,
    orchestrator: CommandOrchestrator,
    on_status_change: Callable[[RunState, RunResult], None] | None = None,
    keyboard_shortcut: str | None = None  # NEW
) -> CmdorcCommandLink:
    link = CmdorcCommandLink(node.config, keyboard_shortcut=keyboard_shortcut)  # NEW

    def update_from_result(handle: RunHandle, context=None):
        result = handle._result

        # NEW: Extract full trigger chain from RunHandle
        trigger_chain = handle.trigger_chain if hasattr(handle, 'trigger_chain') else []
        trigger_source = TriggerSource.from_trigger_chain(trigger_chain)

        link.update_from_run_result(result, trigger_source)
        if on_status_change:
            on_status_change(result.state, result)
        logging.debug(f"Updated {node.name} to {result.state.value} (chain: {trigger_source.format_chain()})")

    # Wire callbacks - pass RunHandle to extract trigger_chain
    orchestrator.set_lifecycle_callback(
        node.name,
        on_success=update_from_result,
        on_failed=update_from_result,
        on_cancelled=update_from_result
    )
    orchestrator.on_event(
        f"command_started:{node.name}",
        lambda h, ctx: update_from_result(h) if h else None
    )

    return link
```
- Test: `test_integrator.py` – Mock RunHandle with trigger_chain, create link, simulate callbacks, assert update called with full trigger chain.

Rationale: NEW: Wires tooltips with full trigger chains from cmdorc's RunHandle.trigger_chain property.

### Step 7: TUI App Global Keyboard Handler (2-3 hours)
- In `textual_cmdorc/app.py`: Add on_key() handler for global keyboard shortcuts.
```python
# In CmdorcApp.__init__
def __init__(self, config_path: str = "config.toml", **kwargs):
    super().__init__(**kwargs)
    setup_logging()

    # NEW: Load with keyboard config
    runner_config, self.keyboard_config, watchers, self.hierarchy = load_frontend_config(config_path)
    self.orchestrator = CommandOrchestrator(runner_config)

    # NEW: Build key -> command_name lookup
    self.key_to_command: Dict[str, str] = {}
    if self.keyboard_config.enabled:
        self.key_to_command = {
            key: cmd_name
            for cmd_name, key in self.keyboard_config.shortcuts.items()
        }

# NEW: Global keyboard handler
def on_key(self, event: Key) -> None:
    """Handle global keyboard shortcuts for commands."""
    if not self.keyboard_config.enabled:
        return

    key = event.key

    if key in self.key_to_command:
        command_name = self.key_to_command[key]

        # Find widget for this command
        command_links = list(self.query(CmdorcCommandLink))
        target_link = None
        for link in command_links:
            if link.config.name == command_name:
                target_link = link
                break

        if target_link:
            # Use smart action that handles running/stopped state
            target_link.action_play_stop()
            event.prevent_default()
            event.stop()

            # Optional: Log to log pane
            if hasattr(self, 'log_pane'):
                self.log_pane.write_line(f"[{key}] triggered: {command_name}")
        else:
            # NEW: Write to log pane for better user feedback
            if hasattr(self, 'log_pane'):
                self.log_pane.write_line(f"⚠️ Shortcut [{key}] ignored: Command '{command_name}' not found in tree")
            logging.warning(f"Shortcut '{key}' -> '{command_name}' but widget not found")

# In build_command_tree() method
def build_command_tree(self, tree: Tree, nodes: list[CommandNode], parent=None):
    for node in nodes:
        # Get keyboard shortcut for this command
        shortcut = self.keyboard_config.shortcuts.get(node.name) if self.keyboard_config.enabled else None

        # Create link with shortcut
        link = create_command_link(node, self.orchestrator, self.on_global_status_change, keyboard_shortcut=shortcut)
        link._update_tooltips()  # Refresh tooltips

        # Add to tree
        if parent is None:
            tree_node = tree.root.add(link)
        else:
            tree_node = parent.add(link)

        # Recursively add children
        if node.children:
            self.build_command_tree(tree, node.children, tree_node)
```
- Test: `test_app.py` – Create app, press keys, assert commands triggered. Test keyboard_config disabling.

Rationale: NEW: Global keyboard shortcuts integrate textual-filelink's action_play_stop() with app-level key handling.

### Step 8: Tests & Coverage Enforcement (5-8 hours)
- Achieve ≥90% coverage: Unit for pure logic, integration for app.
- Errors: Catch/log (e.g., invalid paths, concurrency limits).
- CI: Update ci.yml with `--cov-fail-under=90`.

Rationale: Enforces quality.

### Step 9: Documentation & Examples (2-4 hours)
- Update README.md with features, install, quick start. **NEW:** Include keyboard shortcuts and trigger chains features. Show `cmdorc init` command.
- Add examples/config.toml with `[keyboard]` section, `[[file_watcher]]` section, and sample commands.
- Update architecture.md with new features.

## Summary of New Features

This implementation adds two major features to textual-cmdorc:

1. **Trigger Chain Breadcrumbs (Breadcrumb Display):**
   - Captures full trigger chain from `RunHandle.trigger_chain`
   - Displays in tooltips: "py_file_changed → command_success:Lint → command_success:Format"
   - Supports optional left truncation if chain is too long

2. **Global Keyboard Shortcuts:**
   - Configurable in `[keyboard]` section of TOML config
   - Default to number keys 1-9, but customizable to any key
   - Show hints in tooltips for unconfigured commands
   - Work from anywhere in the app (global, not just when focused)

## Next Steps
- Commit per step.
- Run `pdm run ruff check . && pdm run pytest`.
- Questions? Refer to architecture.md or implementation.md.