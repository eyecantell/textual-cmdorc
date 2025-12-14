# tc_architecture.md — textual-cmdorc Architecture Reference  
**Version:** 0.1.0 (Pre-implementation)  
**Status:** Authoritative design document — supersedes all prior discussion

This is the single source of truth for `textual-cmdorc`’s architecture, responsibilities, and public contracts.

---

## 1. Design Principles

| Principle                        | Rationale                                                                                           |
|----------------------------------|-----------------------------------------------------------------------------------------------------|
| **cmdorc is the only source of truth** | All state, execution, triggers, and history live in `CommandOrchestrator`. The TUI is purely a viewer/controller. |
| **Zero hidden mutations**        | All UI updates are driven by explicit callbacks from `cmdorc` (lifecycle + `on_event`). No polling. |
| **Separation of concerns**       | - Config → `cmdorc_frontend/config.py`<br>- Hierarchy → `cmdorc_frontend/config.py`<br>- File watching → `textual_cmdorc/file_watcher.py` (concrete) + `cmdorc_frontend/watchers.py` (abstract)<br>- Widget wiring → `textual_cmdorc/integrator.py`<br>- UI → `textual_cmdorc/app.py` |
| **Testability first**            | Every non-UI component is pure or mockable. UI tested with Textual’s testing utilities. ≥90% coverage enforced. |
| **Graceful degradation**         | If `[[file_watcher]]` missing → no watchers started. If `CommandLink` missing features → fall back to defaults or log warnings. |
| **Extensibility**                | New trigger sources (HTTP, Git hooks, etc.) only need to call `orchestrator.trigger()`. |

---

## 2. Public Entry Point

```python
# Recommended usage
textual run textual_cmdorc.app --config path/to/config.toml
```

```python
# Programmatic
from textual_cmdorc import CmdorcApp
app = CmdorcApp(config_path="config.toml")
app.run()
```

Only one public class is exposed: `CmdorcApp`.

---

## 3. Component Diagram & Responsibilities

```
+-------------------+       +-----------------------+       +---------------------+
|   CmdorcApp       | <---> | CommandOrchestrator   | <---> | LocalSubprocessExec |
| (Textual App)     |       | (cmdorc backend)      |       +---------------------+
+-------------------+       +-----------------------+
       ^   ^   ^                     ^      ^
       |   |   |                     |      |
       |   |   |                     |      +-------------------+
       |   |   |                     |                          |
       |   |   |              +------+------+           +-------+---------+
       |   |   +------------> | FileWatcher |           | CommandLink     |
       |   |                  |  Manager     |           | (textual-filelink)|
       |   |                  +-------------+           +-----------------+
       |   |
       |   +----------------> ConfigParser (TOML + hierarchy + watchers)
       |
       +--------------------> Integrator (wires callbacks, tooltips, output_path)
```

| Component                    | Owns                                                                 | Does NOT Own                                  |
|------------------------------|----------------------------------------------------------------------|-----------------------------------------------|
| **CmdorcApp**                | Textual lifecycle, layout, global hotkeys, log pane                  | Command execution, file watching logic        |
| **ConfigParser**             | Load TOML → `RunnerConfig` + `list[FileWatcherConfig]` + hierarchy  | UI rendering                                  |
| **FileWatcherManager**       | Starts/stops `watchdog` observers, debounced `orchestrator.trigger()`| UI, command state                             |
| **Integrator**               | Creates `CmdorcCommandLink`, wires cmdorc lifecycle callbacks        | File watching, config parsing                 |
| **CmdorcCommandLink**        | Subclass of `CommandLink`; adds `current_trigger`, dynamic tooltips | Execution logic                               |

---

## 4. Data Flow & Method Call Graph

### 4.1 Startup Sequence
```mermaid
sequenceDiagram
    participant User->>CmdorcApp: __init__(config_path)
    CmdorcApp->>ConfigParser: load_runner_and_watchers()
    ConfigParser-->>CmdorcApp: RunnerConfig, [FileWatcherConfig], hierarchy
    CmdorcApp->>CommandOrchestrator: __init__(runner_config)
    CmdorcApp->>FileWatcherManager: __init__(orchestrator)
    CmdorcApp->>CmdorcApp: on_mount()
    CmdorcApp->>FileWatcherManager: add_watcher() × N
    CmdorcApp->>FileWatcherManager: start()
    CmdorcApp->>Integrator: create_command_link() for each node
    Integrator->>CmdorcCommandLink: __init__ + set_lifecycle_callback() + on_event()
    CmdorcApp->>Integrator: reconcile_link() for each link  # NEW: State sync
```

### 4.2 File Change → Trigger
```mermaid
sequenceDiagram
    Filesystem->>watchdog: file_modified
    watchdog->>_DebouncedHandler: on_any_event()
    _DebouncedHandler->>asyncio: call_soon_threadsafe(schedule delayed trigger)
    _DebouncedHandler->>CommandOrchestrator: trigger("py_file_changed")
    CommandOrchestrator-->>Integrator callbacks: command_started:XYZ etc.
    Integrator->>CmdorcCommandLink: apply_update(PresentationUpdate(...))
```

### 4.3 Manual Play/Stop Click
```mermaid
sequenceDiagram
    User->>CmdorcCommandLink: PlayClicked / StopClicked
    CmdorcCommandLink->>CmdorcApp: on_command_link_play/stop_clicked()
    CmdorcApp->>CommandOrchestrator: run_command(name)  or  cancel_command(name)
    Note right of CmdorcApp: run_command is fire-and-forget; status updates arrive via callbacks
```

### 4.4 Tooltip Logic (Dynamic)
```python
class CmdorcCommandLink(CommandLink):
    current_trigger: TriggerSource = TriggerSource("Idle", "manual")

    def _update_tooltips(self) -> None:
        if self.is_running:
            self.set_stop_tooltip(f"Stop — Running because: {self.current_trigger.name} ({self.current_trigger.kind})")
        else:
            triggers = ", ".join(self.config.triggers) or "none"
            self.set_play_tooltip(f"Run (Triggers: {triggers} | manual)")
```

Trigger source is captured in the `on_event` callback using `TriggerContext` (cmdorc passes it on lifecycle events).

---

## 5. Configuration Extensions

```toml
# Existing cmdorc [[command]] tables unchanged

# New optional section — may appear zero or more times
[[file_watcher]]
dir = "./src"                    # required
patterns = ["**/*.py", "**/*.pyi"]  # optional, takes precedence
extensions = [".py"]             # optional, fallback
ignore_dirs = ["__pycache__", ".git"]
trigger = "py_file_changed"      # required — cmdorc event name
debounce_ms = 300                # optional, default 300
```

---

## 6. Key Classes & Public Contracts

### `src/textual_cmdorc/config_parser.py`
```python
def load_runner_and_watchers(
    config_path: str | Path
) -> tuple[RunnerConfig, list[FileWatcherConfig], list[CommandNode]]:
    """Single function used by the app. Returns everything needed."""
```

### `src/textual_cmdorc/file_watcher.py`
```python
@dataclass(frozen=True)
class FileWatcherConfig:
    dir: Path
    patterns: list[str] | None = None
    extensions: list[str] | None = None
    ignore_dirs: list[str] | None = None
    trigger: str = ""
    debounce_ms: int = 300

class FileWatcherManager:
    def __init__(self, orchestrator: CommandOrchestrator, loop: asyncio.AbstractEventLoop)
    def add_watcher(self, cfg: FileWatcherConfig) -> None
    def start(self) -> None
    def stop(self) -> None
```

### `src/textual_cmdorc/widgets.py`
```python
@dataclass
class TriggerSource:
    name: str
    kind: Literal["manual", "file", "lifecycle"]

class CmdorcCommandLink(CommandLink):
    config: CommandConfig
    current_trigger: TriggerSource = TriggerSource("Idle", "manual")

    def apply_update(self, update: PresentationUpdate) -> None
    def _update_tooltips(self) -> None
```

### `src/textual_cmdorc/integrator.py`
```python
@dataclass
class PresentationUpdate:
    icon: str
    running: bool
    tooltip: str
    output_path: Path | None

class StateReconciler:
    def __init__(self, orchestrator: CommandOrchestrator)
    def reconcile_link(self, link: CmdorcCommandLink) -> None

def create_command_link(
    node: CommandNode,
    orchestrator: CommandOrchestrator,
) -> CmdorcCommandLink:
    """Factory used by the app. Fully wires all callbacks."""
```

### `src/textual_cmdorc/app.py`
```python
class CmdorcApp(App):
    def __init__(self, config_path: str = "config.toml", **kwargs)
    async def on_mount(self) -> None
    async def action_quit(self) -> None
    # Event handlers for PlayClicked, StopClicked, Input.Submitted
```

---

## 7. Testing Strategy (≥90% coverage)

| Module                  | Target | Method                              |
|-------------------------|--------|-------------------------------------|
| config_parser.py        | 100%   | Pure → table-driven tests           |
| file_watcher.py         | 98%    | Mock observer + asyncio sleep tests |
| integrator.py           | 95%    | Mock orchestrator, assert callbacks |
| widgets.py              | 92%    | Textual test utilities + reactive   |
| app.py                  | 88%+   | Integration tests with mounted app  |

CI will fail if total coverage < 90%. Add contract tests: Mock cmdorc → assert PresentationUpdate; Mock integrator → assert widget updates. Add golden-path snapshot test for Tree layout.

---

## 8. Implementation Order (for implementation.md)

1. Project setup & pyproject.toml (watchdog dep)
2. `config_parser.py` → add `[[file_watcher]]` parsing
3. `file_watcher.py` → complete `FileWatcherManager`
4. `widgets.py` → `CmdorcCommandLink` with dynamic tooltips
5. `integrator.py` → enhanced callback wiring including trigger source
6. `app.py` → integrate everything, mount/stop watchers, tree building
7. Tests & coverage enforcement
8. Documentation & examples

## 9. Invariants

- textual-cmdorc never infers command state. It only reflects state transitions reported by cmdorc.
- Cycles are detected and broken arbitrarily; commands involved in cycles may not appear in all branches.
- StateReconciler is idempotent, read-only, and never triggers execution.
- StateReconciler runs once on mount after tree is built. It does not poll or run continuously.
- Reconciliation handles the case where cmdorc has state (running commands, history) but the TUI just started and hasn't received lifecycle callbacks yet.

---
