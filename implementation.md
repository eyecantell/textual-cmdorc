
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
│   ├── textual_cmdorc/
│   │   ├── __init__.py
│   │   ├── app.py              # Main Textual App
│   │   ├── config_parser.py    # Parse TOML, build hierarchy (with duplication for multi-parents)
│   │   ├── file_watcher.py     # FileWatcherManager for watchdog integration
│   │   ├── widgets.py          # Custom CmdorcCommandLink
│   │   ├── integrator.py       # Factory to create/wire CommandLink with cmdorc
│   │   └── utils.py            # Logging, state mappers
├── examples/
│   └── config.toml             # Query example
├── pyproject.toml              # Dependencies: textual, textual-filelink, cmdorc, watchdog
├── README.md                   # Usage
├── LICENSE                     # MIT
└── tests/
    ├── test_config_parser.py   # Hierarchy and watcher config tests
    ├── test_file_watcher.py    # Watcher tests
    ├── test_integrator.py      # Widget wiring tests
    ├── test_widgets.py         # CmdorcCommandLink tests
    └── test_app.py             # TUI integration tests
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
- In `__init__.py`: `from .app import CmdorcApp`
- In `utils.py`: Basic logging and helpers.
```python
# src/textual_cmdorc/utils.py
import logging
from dataclasses import dataclass
from typing import Literal
from pathlib import Path
from cmdorc import RunResult

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

@dataclass
class TriggerSource:
    name: str
    kind: Literal["manual", "file", "lifecycle"]

def map_run_state_to_icon(state: 'RunState') -> str:
    # Map cmdorc.RunState to CommandLink icons (defaults from README)
    if state == RunState.SUCCESS: return "✅"
    if state == RunState.FAILED: return "❌"
    if state == RunState.CANCELLED: return "⏹"
    return "❓"  # Pending/Idle

@dataclass
class PresentationUpdate:
    icon: str
    running: bool
    tooltip: str
    output_path: Path | None = None
```
- Test: `pdm run python -m textual_cmdorc` (expect error if incomplete). Run `pdm run ruff check .` for linting.

Rationale: Sets up PDM, logging for debug; mapper for status icons.

### Step 2: Config Parsing and Hierarchy Building (5-8 hours)
- In `config_parser.py`: Load TOML via cmdorc's `load_config`, build tree with duplication for multi-parents. Also parse `[[file_watcher]]`.
- Use tomllib/tomli for raw parsing to extract watchers (since load_config doesn't handle custom sections).
```python
# src/textual_cmdorc/config_parser.py
from typing import Dict, List, Tuple
from pathlib import Path
from dataclasses import dataclass
import re
import tomllib  # or tomli for <3.11
from cmdorc import load_config, CommandConfig, RunnerConfig
from .file_watcher import FileWatcherConfig

@dataclass
class CommandNode:
    config: CommandConfig
    children: List['CommandNode'] = None  # type: ignore

    def __post_init__(self):
        self.children = []

def load_runner_and_watchers(config_path: str | Path) -> Tuple[RunnerConfig, List[FileWatcherConfig], List[CommandNode]]:
    path = Path(config_path)
    raw = tomllib.loads(path.read_text())
    
    # Parse watchers
    watchers = [
        FileWatcherConfig(
            dir=path.parent / Path(w["dir"]),
            patterns=w.get("patterns"),
            extensions=w.get("extensions"),
            ignore_dirs=w.get("ignore_dirs", ["__pycache__", ".git"]),
            trigger=w["trigger"],
            debounce_ms=w.get("debounce_ms", 300),
        )
        for w in raw.get("file_watcher", [])
    ]
    
    # Use cmdorc for runner_config
    runner_config = load_config(config_path)
    
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
        node = CommandNode(commands[name])
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
- Test: `test_config_parser.py` – Use example config.toml, assert hierarchy (Lint → Format → Tests; Another Command). Add tests for watcher parsing, multi-parents, cycles.

Rationale: Handles custom [[file_watcher]]; duplication for DAGs.

### Step 3: File Watcher Implementation (3-5 hours)
- In `file_watcher.py`: Use watchdog with PollingObserver for cross-platform.
```python
# src/textual_cmdorc/file_watcher.py
from dataclasses import dataclass
from pathlib import Path
from typing import List
import asyncio
import logging
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers.polling import PollingObserver as Observer
from cmdorc import CommandOrchestrator

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class FileWatcherConfig:
    dir: Path
    patterns: List[str] | None = None
    extensions: List[str] | None = None
    ignore_dirs: List[str] | None = None
    trigger: str = ""
    debounce_ms: int = 300

class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, trigger: str, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop, debounce_ms: int = 300):
        self.trigger = trigger
        self.orchestrator = orchestrator
        self.loop = loop
        self.debounce_ms = debounce_ms
        self._tasks: dict[str, asyncio.Task] = {}

    def _schedule(self, event: FileSystemEvent):
        key = self.trigger  # Changed to per-watcher debounce
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

class FileWatcherManager:
    def __init__(self, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop):
        self.orchestrator = orchestrator
        self.loop = loop
        self.observer = Observer()
        self.handlers: List[_DebouncedHandler] = []

    def add_watcher(self, config: FileWatcherConfig) -> None:
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

Rationale: Debounced, cross-platform triggering; only interacts via orchestrator.trigger().

### Step 5: Integrator Implementation (2-4 hours)
- In `integrator.py`: Factory to wire callbacks, capturing trigger source.
```python
# src/textual_cmdorc/integrator.py
from typing import Callable
from cmdorc import CommandOrchestrator, RunHandle, RunResult, RunState
from .widgets import CmdorcCommandLink, TriggerSource
from .config_parser import CommandNode
import logging

class StateReconciler:
    def __init__(self, orchestrator: CommandOrchestrator):
        self.orchestrator = orchestrator
    
    def reconcile_link(self, link: CmdorcCommandLink) -> None:
        """Sync link state with current cmdorc state. Idempotent."""
        active_handles = self.orchestrator.get_active_handles(link.config.name)
        
        if active_handles:
            handle = active_handles[-1]
            if handle.is_finalized and hasattr(handle, '_result'):
                # Handle finished but not cleaned up yet
                result = handle._result
                trigger_source = TriggerSource("recovered", "lifecycle")
                link.update_from_run_result(result, trigger_source)
            else:
                # Still running
                comment = getattr(handle, 'comment', 'Running')
                link.set_status(running=True, tooltip=f"Running: {comment}")
        else:
            # No active runs - check history for last state
            history = self.orchestrator.get_history(link.config.name, limit=1)
            if history:
                result = history[0]
                link.update_from_run_result(result, TriggerSource("recovered", "lifecycle"))

def create_command_link(
    node: 'CommandNode',
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
        logging.debug(f"Updated {node.config.name} to {result.state.value}")
    
    # Wire callbacks
    orchestrator.set_lifecycle_callback(
        node.config.name,
        on_success=lambda h, ctx: update_from_result(h._result, ctx),
        on_failed=lambda h, ctx: update_from_result(h._result, ctx),
        on_cancelled=lambda h, ctx: update_from_result(h._result, ctx)
    )
    orchestrator.on_event(
        f"command_started:{node.config.name}",
        lambda h, ctx: update_from_result(h._result, ctx) if h else None
    )
    
    return link
```
- Test: `test_integrator.py` – Mock orchestrator/context, create link, simulate callbacks, assert update called with source.

Rationale: Wires tooltips with trigger context from TriggerContext.

### Step 5: Main App Implementation (6-10 hours)
- In `app.py`: Integrate all, with watcher start/stop. Use Tree for hierarchy.
```python
# src/textual_cmdorc/app.py
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Tree, Log, Input, Footer
from textual.reactive import reactive
from cmdorc import CommandOrchestrator, RunState
from .config_parser import load_runner_and_watchers, CommandNode
from .file_watcher import FileWatcherManager
from .integrator import create_command_link, StateReconciler
from .utils import setup_logging
from textual_filelink import CommandLink
import asyncio

class CmdorcApp(App):
    config_path = reactive("examples/config.toml")
    
    BINDINGS = [
        ("r", "reload_config", "Reload config"),
        ("ctrl+c", "cancel_all", "Cancel all"),
        ("ctrl+p", "toggle_log", "Toggle log pane"),
        ("?", "show_help", "Show help"),
    ]
    
    def __init__(self, config_path: str = "examples/config.toml", **kwargs):
        super().__init__(**kwargs)
        setup_logging()
        self.config_path_str = config_path
        self.runner_config, self.watcher_configs, self.hierarchy = load_runner_and_watchers(self.config_path_str)
        self.orchestrator = CommandOrchestrator(self.runner_config)
        self.loop = asyncio.get_event_loop()
        self.watcher_manager = FileWatcherManager(self.orchestrator, self.loop)
        self.link_registry: dict[str, list[CmdorcCommandLink]] = {}  # For broadcasting to duplicates
        self.reconciler = StateReconciler(self.orchestrator)
    
    async def on_mount(self) -> None:
        for wc in self.watcher_configs:
            self.watcher_manager.add_watcher(wc)
        self.watcher_manager.start()
        # Reconcile after tree build
        for links in self.link_registry.values():
            for link in links:
                self.reconciler.reconcile_link(link)

    def compose(self) -> ComposeResult:
        self.command_tree = Tree("Commands")
        self.build_command_tree(self.command_tree, self.hierarchy)
        
        yield self.command_tree
        self.log_pane = Log(id="log")
        yield self.log_pane
        self.trigger_input = Input(placeholder="Enter trigger (e.g., py_file_changed)")
        yield self.trigger_input
        yield Footer()
    
    def build_command_tree(self, tree: Tree, nodes: list[CommandNode], parent=None):
        for node in nodes:
            link = create_command_link(node, self.orchestrator, self.on_global_status_change)
            existing = self.link_registry.get(node.config.name, [])
            if existing:
                link.label = f"{link.label} ({len(existing) + 1})"
            self.link_registry.setdefault(node.config.name, []).append(link)
            tree_node = tree.add(link, parent=parent)  # CommandLink as label
            self.build_command_tree(tree, node.children, parent=tree_node)
    
    def on_global_status_change(self, state: RunState, result: RunResult):
        self.post_message(LogEvent(f"{result.command_name}: {state.value} ({result.duration_str})\n{result.output[:100]}..."))
    
    async def on_input_submitted(self, message: Input.Submitted):
        await self.orchestrator.trigger(message.value)
        self.post_message(LogEvent(f"Triggered: {message.value}"))
    
    def on_command_link_play_clicked(self, event: CommandLink.PlayClicked):
        self.run_worker(self._run_command(event.name))
    
    async def _run_command(self, name: str):
        handle: 'RunHandle' = await self.orchestrator.run_command(name)
        await handle.wait()
    
    def on_command_link_stop_clicked(self, event: CommandLink.StopClicked):
        self.run_worker(self.orchestrator.cancel_command(event.name, comment="Manual stop"))
    
    async def action_reload_config(self):
        """Reload configuration from disk."""
        self.runner_config, self.watcher_configs, self.hierarchy = load_runner_and_watchers(self.config_path_str)
        self.command_tree.clear()
        self.link_registry = {}
        self.build_command_tree(self.command_tree, self.hierarchy)
        self.notify("Configuration reloaded", severity="information")
    
    async def action_cancel_all(self):
        """Cancel all running commands."""
        await self.orchestrator.cancel_all()
        self.notify("All commands cancelled", severity="warning")

    def action_toggle_log(self):
        """Toggle log pane visibility."""
        self.log_pane.display = not self.log_pane.display

    def action_show_help(self):
        """Show help screen."""
        self.notify("Help: r=reload, Ctrl+C=cancel all, Ctrl+P=toggle log, ?=help", timeout=5)
    
    async def action_quit(self) -> None:
        self.watcher_manager.stop()
        await self.orchestrator.shutdown()
        await super().action_quit()
    
    # New for structured logs
    class LogEvent(Message):
        def __init__(self, text: str):
            self.text = text
    
    def on_log_event(self, event: LogEvent):
        self.log_pane.write_line(event.text)
```
- Test: `test_app.py` – Mount app, simulate file changes/triggers/clicks, assert logs/UI updates (use Tree methods like expand/collapse in tests).

Rationale: Uses Tree for proper hierarchy, interactivity, and future collapsibility. Integrates watchers; reload for dynamic configs.

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