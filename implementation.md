
# Development Plan for textual-cmdorc

## Overview
textual-cmdorc is a Textual-based Terminal User Interface (TUI) that acts as a frontend for the cmdorc library. It loads a TOML configuration file (e.g., config.toml), parses the commands and their lifecycle triggers (specifically "command_success:<name>", "command_failed:<name>", and "command_cancelled:<name>"), and dynamically generates a hierarchical tree of CommandLink widgets (from textual-filelink) using Textual's Tree widget. The hierarchy indents child commands under parents based on these triggers, duplicating commands in the tree if they have multiple parents (treating the structure as a DAG with duplication to form trees).

The TUI will:
- Display commands in an indented hierarchy (e.g., Lint → Format → Tests, with "Another Command" as a root) using Tree for better interactivity and collapsibility.
- Use CommandLink widgets for each command, showing status (e.g., spinner for running, icons for success/failed/cancelled).
- Update statuses in real-time via cmdorc's lifecycle callbacks.
- Allow manual run/stop via CommandLink's play/stop buttons.
- Handle automatic triggering, with the output file path set on the CommandLink for viewing results (latest run only).
- Include a log pane for events/output snippets and an input for manual triggers.
- Support file watching via watchdog to trigger events on file changes (e.g., "py_file_changed" on *.py modifications).
- Graceful shutdown on app close.

This plan is for a junior developer: Step-by-step, with code snippets, testing, and rationale. Assume Python/Textual/async basics. Estimated effort: 25-45 hours.

### Prerequisites
- Python 3.10+.
- Install: `pdm install` or `pip install textual textual-filelink cmdorc watchdog`.
- Read:
  - cmdorc: README.md and architecture.md.
  - textual-filelink: README.md (focus on CommandLink API: constructor, set_status, set_output_path, events like PlayClicked).
  - Textual docs: https://textual.textualize.io/ (widgets: Tree, Log, Input; events; workers for async).
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

## Step-by-Step Implementation

### Step 1: Project Setup & Boilerplate (1-2 hours)
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
    name: str
    kind: Literal["manual", "file", "lifecycle"]

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
- In `cmdorc_frontend/config.py`: Load TOML, build hierarchy, watchers.
```python
# src/cmdorc_frontend/config.py
from typing import Dict, List, Tuple
from pathlib import Path
import re
import tomllib  # or tomli for <3.11
import logging
from cmdorc import load_config as load_cmdorc_config, RunnerConfig, CommandConfig
from .models import CommandNode
from .watchers import WatcherConfig

def load_frontend_config(path: str | Path) -> Tuple[RunnerConfig, List[WatcherConfig], List[CommandNode]]:
    """Load configuration for any frontend."""
    path = Path(path)
    raw = tomllib.loads(path.read_text())
    
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
    
    return runner_config, watchers, roots
```
- Test: `test_config.py` – Use example config.toml, assert hierarchy, watchers.

Rationale: Shared config logic for any frontend.

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
- In `textual_cmdorc/widgets.py`: CmdorcCommandLink implementing CommandView.
```python
# src/textual_cmdorc/widgets.py
from textual_filelink import CommandLink
from cmdorc import CommandConfig, RunResult, RunState
from cmdorc_frontend.state_manager import CommandView
from cmdorc_frontend.models import TriggerSource, PresentationUpdate, map_run_state_to_icon

class CmdorcCommandLink(CommandLink, CommandView):
    def __init__(self, config: CommandConfig, **kwargs):
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
        self.current_trigger: TriggerSource = TriggerSource("Idle", "manual")
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
        tooltip = f"{result.state.value} ({result.duration_str})"
        update = PresentationUpdate(icon=icon, running=(result.state == RunState.RUNNING), tooltip=tooltip, output_path=result.output if result.state in [RunState.SUCCESS, RunState.FAILED, RunState.CANCELLED] else None)
        self.apply_update(update)
        self.current_trigger = trigger_source
        self._update_tooltips()

    def _update_tooltips(self) -> None:
        if self.is_running:
            self.set_stop_tooltip(f"Stop — Running because: {self.current_trigger.name} ({self.current_trigger.kind})")
        else:
            triggers = ", ".join(self.config.triggers) or "none"
            self.set_play_tooltip(f"Run (Triggers: {triggers} | manual)")
```
- Test: `test_widgets.py` – Create link, call update_from_run_result, assert tooltips/status set.

Rationale: Adds dynamic tooltips with triggers; handles output path.

### Step 6: TUI Integrator (2-3 hours)
- In `textual_cmdorc/integrator.py`: TUI-specific wiring.
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
    on_status_change: Callable[[RunState, RunResult], None] | None = None
) -> CmdorcCommandLink:
    link = CmdorcCommandLink(node.config)
    
    def update_from_result(result: RunResult, context=None):
        source_name = context.get('trigger', 'manual') if context else 'manual'
        kind = "lifecycle" if "command_" in source_name else ("file" if "file" in source_name else "manual")
        trigger_source = TriggerSource(source_name, kind)
        link.update_from_run_result(result, trigger_source)
        if on_status_change:
            on_status_change(result.state, result)
        logging.debug(f"Updated {node.name} to {result.state.value}")
    
    # Wire callbacks
    orchestrator.set_lifecycle_callback(
        node.name,
        on_success=lambda h, ctx: update_from_result(h._result, ctx),
        on_failed=lambda h, ctx: update_from_result(h._result, ctx),
        on_cancelled=lambda h, ctx: update_from_result(h._result, ctx)
    )
    orchestrator.on_event(
        f"command_started:{node.name}",
        lambda h, ctx: update_from_result(h._result, ctx) if h else None
    )
    
    return link
```
- Test: `test_integrator.py` – Mock orchestrator/context, create link, simulate callbacks, assert update called with source.

Rationale: Wires tooltips with trigger context from TriggerContext.

### Step 7: Tests & Coverage Enforcement (5-8 hours)
- Achieve ≥90% coverage: Unit for pure logic, integration for app.
- Errors: Catch/log (e.g., invalid paths, concurrency limits).
- CI: Update ci.yml with `--cov-fail-under=90`.

Rationale: Enforces quality.

### Step 8: Documentation & Examples (2-4 hours)
- Update README.md with skeletal content: Features, install, quick start.
- Add examples/config.toml with [[file_watcher]].

## Next Steps
- Commit per step.
- Run `pdm run ruff check . && pdm run pytest`.
- Questions? Refer to tc_architecture.md or ask senior.