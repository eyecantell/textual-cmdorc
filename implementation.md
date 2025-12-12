# Development Plan for textual-cmdorc

## Overview
textual-cmdorc is a Textual-based Terminal User Interface (TUI) that acts as a frontend for the cmdorc library. It loads a TOML configuration file (e.g., config.toml), parses the commands and their lifecycle triggers (specifically "command_success:<name>", "command_failed:<name>", and "command_cancelled:<name>"), and dynamically generates a hierarchical list of CommandLink widgets (from textual-filelink). The hierarchy indents child commands under parents based on these triggers, duplicating commands in the tree if they have multiple parents (treating the structure as a DAG with duplication to form trees).

The TUI will:
- Display commands in an indented hierarchy (e.g., Lint → Format → Tests, with "Another Command" as a root).
- Use CommandLink widgets for each command, showing status (e.g., spinner for running, icons for success/failed/cancelled).
- Update statuses in real-time via cmdorc's lifecycle callbacks.
- Allow manual run/stop via CommandLink's play/stop buttons.
- Handle automatic triggering, with the output file path set on the CommandLink for viewing results (latest run only).
- Include a log pane for events/output snippets and an input for manual triggers.
- Graceful shutdown on app close.

This plan is for a junior developer: Step-by-step, with code snippets, testing, and rationale. Assume Python/Textual/async basics. Estimated effort: 25-45 hours.

### Prerequisites
- Python 3.10+.
- Install: `pdm install` or `pip install textual textual-filelink cmdorc`.
- Read:
  - cmdorc: README.md and architecture.md (from query).
  - textual-filelink: Provided README.md (focus on CommandLink API: constructor, set_status, set_output_path, events like PlayClicked).
  - Textual docs: https://textual.textualize.io/ (widgets: Vertical, Log, Input; events; workers for async).

### Project Structure
```
textual-cmdorc/
├── src/
│   ├── textual_cmdorc/
│   │   ├── __init__.py
│   │   ├── app.py              # Main Textual App
│   │   ├── config_parser.py    # Parse TOML, build hierarchy (with duplication for multi-parents)
│   │   ├── widgets.py          # Custom CmdorcCommandLink if needed
│   │   ├── integrator.py       # Factory to create/wire CommandLink with cmdorc
│   │   └── utils.py            # Logging, state mappers
├── examples/
│   └── config.toml             # Query example
├── pyproject.toml              # Dependencies: textual, textual-filelink, cmdorc
├── README.md                   # Usage
├── LICENSE                     # MIT
└── tests/
    ├── test_config_parser.py   # Hierarchy tests
    ├── test_integrator.py      # Widget wiring tests
    └── test_app.py             # TUI integration tests
```

pyproject.toml excerpt:
```toml
[project]
name = "textual-cmdorc"
version = "0.1.0"
dependencies = ["textual>=0.47.0", "textual-filelink>=0.2.0", "cmdorc>=0.1.0"]

[tool.pdm.dev-dependencies]
test = ["pytest", "pytest-asyncio"]
```

## Step-by-Step Implementation

### Step 1: Setup and Boilerplate (1-2 hours)
- Create structure.
- In `__init__.py`: `from .app import CmdorcApp`
- In `utils.py`: Basic logging.
```python
# src/textual_cmdorc/utils.py
import logging

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

def map_run_state_to_icon(state: 'RunState') -> str:
    # Map cmdorc.RunState to CommandLink icons (defaults from README)
    if state == 'SUCCESS': return "✅"
    if state == 'FAILED': return "❌"
    if state == 'CANCELLED': return "⏹"
    return "❓"  # Pending/Idle
```
- Test: `pdm run python -m textual_cmdorc` (expect error if incomplete).

Rationale: Logging for debug; mapper for status icons (use defaults per Q7).

### Step 2: Config Parsing and Hierarchy Building (5-8 hours)
- In `config_parser.py`: Load TOML via cmdorc's `load_config`, build tree with duplication for multi-parents.
- Triggers: Parse "command_success:<name>", "command_failed:<name>", "command_cancelled:<name>" as edges (parent → child).
- If cycle or multi-parents, duplicate nodes (create separate subtrees).
- Use a recursive Node class.

```python
# src/textual_cmdorc/config_parser.py
from typing import Dict, List
from cmdorc import load_config, CommandConfig, RunnerConfig
import re
from dataclasses import dataclass

@dataclass
class CommandNode:
    config: CommandConfig
    children: List['CommandNode'] = None  # type: ignore

    def __post_init__(self):
        self.children = []

def build_hierarchy(config_path: str) -> List[CommandNode]:
    runner_config: RunnerConfig = load_config(config_path)
    commands: Dict[str, CommandConfig] = {c.name: c for c in runner_config.commands}
    
    # Build graph: parent -> [children] for each trigger type
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
    
    # To handle multi-parents/duplication: Use DFS/BFS to build trees, duplicating subtrees
    visited: set[str] = set()
    roots: List[CommandNode] = []
    
    def build_node(name: str, visited_local: set[str]) -> CommandNode | None:
        if name in visited_local:
            logging.warning(f"Cycle detected at {name}, skipping duplicate")
            return None  # Avoid cycles
        visited_local.add(name)
        node = CommandNode(commands[name])
        for child_name in graph.get(name, []):
            child_node = build_node(child_name, visited_local.copy())  # Copy set for branching
            if child_node:
                node.children.append(child_node)
        return node
    
    # Find roots: commands not children of any
    all_children = {c for children in graph.values() for c in children}
    potential_roots = [name for name in commands if name not in all_children]
    
    for root_name in potential_roots:
        if root_name not in visited:
            root_node = build_node(root_name, set())
            if root_node:
                roots.append(root_node)
                visited.add(root_name)  # Mark as visited, but duplicates allowed if multi-entry
    
    return roots
```
- Duplication: By using copy() on visited_local, branches can duplicate if a node is reached multiple ways.
- Test: `test_config_parser.py` – Use example config.toml, assert structure (Lint root with Format child with Tests; Another Command root). Add tests for failed/cancelled triggers and multi-parents (duplicate nodes).

Rationale: Expands to all lifecycle triggers (per Q2). Duplication handles DAGs.

### Step 3: Widget Integration (3-5 hours)
- In `widgets.py`: Subclass CommandLink if needed (e.g., add cmdorc-specific methods).
```python
# src/textual_cmdorc/widgets.py
from textual_filelink import CommandLink
from cmdorc import CommandConfig

class CmdorcCommandLink(CommandLink):
    def __init__(self, config: CommandConfig, **kwargs):
        super().__init__(
            name=config.name,
            output_path=None,  # Set later on completion
            initial_status_icon="❓",
            initial_status_tooltip="Idle",
            show_toggle=False,  # Per example, no toggle
            show_settings=False,  # Optional
            show_remove=False,  # Optional
            **kwargs
        )
        self.config = config
```
- In `integrator.py`: Factory to wire CommandLink with orchestrator callbacks.
```python
# src/textual_cmdorc/integrator.py
from typing import Callable
from cmdorc import CommandOrchestrator, RunHandle, RunResult, RunState
from .widgets import CmdorcCommandLink
from .utils import map_run_state_to_icon
import logging

def create_command_link(
    node: 'CommandNode',
    orchestrator: CommandOrchestrator,
    on_status_change: Callable[['RunState', RunResult], None] | None = None
) -> CmdorcCommandLink:
    link = CmdorcCommandLink(node.config)
    
    def update_from_result(result: RunResult):
        icon = map_run_state_to_icon(result.state.value)
        tooltip = f"{result.state.value} ({result.duration_str})"
        link.set_status(icon=icon, running=(result.state == 'RUNNING'), tooltip=tooltip)
        if result.state in ['SUCCESS', 'FAILED', 'CANCELLED']:
            link.set_output_path(result.output)  # Per Q5/Q6: latest output as path
        if on_status_change:
            on_status_change(result.state, result)
        logging.debug(f"Updated {node.config.name} to {result.state.value}")
    
    # Wire cmdorc callbacks
    orchestrator.set_lifecycle_callback(
        node.config.name,
        on_success=lambda h, _: update_from_result(h._result),
        on_failed=lambda h, _: update_from_result(h._result),
        on_cancelled=lambda h, _: update_from_result(h._result)
    )
    orchestrator.on_event(
        f"command_started:{node.config.name}",
        lambda h, _: update_from_result(h._result) if h else None
    )
    
    return link
```
- Note: Play/Stop handled in app events.
- Test: `test_integrator.py` – Mock orchestrator, create link, simulate callbacks, assert set_status called.

Rationale: Wires updates; output as path per Q5/Q6. No triggers shown per Q3.

### Step 4: Main App Implementation (6-10 hours)
- In `app.py`: Build UI with indented Vertical.
- Recursively add to Vertical with indentation.
```python
# src/textual_cmdorc/app.py
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Log, Input, Footer
from textual.reactive import reactive
from cmdorc import CommandOrchestrator, load_config
from .config_parser import build_hierarchy, CommandNode
from .integrator import create_command_link
from .utils import setup_logging
from textual_filelink import CommandLink
import asyncio

class CmdorcApp(App):
    config_path = reactive("examples/config.toml")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        setup_logging()
        self.hierarchy = build_hierarchy(self.config_path)
        runner_config = load_config(self.config_path)
        self.orchestrator = CommandOrchestrator(runner_config)
    
    def compose(self) -> ComposeResult:
        self.command_list = Vertical(id="command-list")
        self.build_command_tree(self.command_list, self.hierarchy)
        
        yield self.command_list
        self.log_pane = Log(id="log")
        yield self.log_pane
        self.trigger_input = Input(placeholder="Enter trigger (e.g., py_file_changed)")
        yield self.trigger_input
        yield Footer()
    
    def build_command_tree(self, container: Vertical, nodes: list[CommandNode], level: int = 0):
        for node in nodes:
            indent = "  " * level
            link = create_command_link(node, self.orchestrator, self.on_global_status_change)
            link.id = f"cmd-{node.config.name.replace(' ', '-')}"  # Unique ID
            # Wrap in Static for indent (or use CSS padding-left)
            container.mount(Static(f"{indent}- {link}", markup=False))  # Simple text indent
            self.build_command_tree(container, node.children, level + 1)
    
    def on_global_status_change(self, state: 'RunState', result: RunResult):
        self.log_pane.write_line(f"{result.command_name}: {state.value} ({result.duration_str})\n{result.output[:100]}...")
    
    async def on_input_submitted(self, message: Input.Submitted):
        await self.orchestrator.trigger(message.value)
        self.log_pane.write_line(f"Triggered: {message.value}")
    
    def on_command_link_play_clicked(self, event: CommandLink.PlayClicked):
        # Start command async
        self.run_worker(self._run_command(event.name))
    
    async def _run_command(self, name: str):
        handle: 'RunHandle' = await self.orchestrator.run_command(name)
        await handle.wait()  # Wait for completion (or handle in callbacks)
    
    def on_command_link_stop_clicked(self, event: CommandLink.StopClicked):
        await self.orchestrator.cancel_command(event.name, comment="Manual stop")
    
    # Optional: on_command_link_settings_clicked if show_settings=True
    
    async def action_quit(self) -> None:
        await self.orchestrator.shutdown()
        await super().action_quit()
```
- CSS for better indent: Add `Static { padding-left: 2 * level; }` but since dynamic, use Horizontal with Spacer.
- Alternative: Use Textual Tree with str labels, but since CommandLink needs interactivity, stick with Vertical + indent.
- Test: `test_app.py` – Use pytest-asyncio, mount app, simulate triggers, assert log updates.

Rationale: Indented Vertical for full widget interactivity (per Tree limitations). Handles manual/auto.

### Step 5: Error Handling, Polish, and Testing (5-8 hours)
- Errors: Catch in workers, log to pane (e.g., ConcurrencyLimitError).
- Polish: Add reload hotkey ('r') to rebuild hierarchy.
```python
    def key_r(self):
        self.hierarchy = build_hierarchy(self.config_path)
        self.command_list.remove_children()
        self.build_command_tree(self.command_list, self.hierarchy)
```
- Tests: 90% coverage; unit for parser/integrator, integration for app (simulate events).
- Docs: README: `textual run textual_cmdorc.app --config=examples/config.toml`

Rationale: Robustness; per Q1-Q7 integrations.

## Next Steps
- Commit per step.
- Run `pdm run ruff check . && pdm run pytest`.
- Questions? Refer to docs or ask senior.