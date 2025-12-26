# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**textual-cmdorc** is an embeddable TUI frontend for [cmdorc](https://github.com/eyecantell/cmdorc) command orchestration. It displays commands in a flat list with real-time status updates, manual controls, and file watching.

- **Status:** Production ready (59 tests, 29% coverage)
- **Python:** 3.10+
- **Core Dependencies:** Textual 6.6.0+, cmdorc 0.3.0+, watchdog 4.0.0+, textual-filelink 0.4.1+

## Common Development Commands

```bash
# Setup development environment
pdm install -G test -G lint -G dev

# Run all tests with coverage
pdm run pytest --cov

# Run specific test file
pdm run pytest tests/test_cli.py -v

# Run single test
pdm run pytest tests/test_cli.py::test_name -v

# Lint code
pdm run ruff check .

# Format code
pdm run ruff format .

# Type checking
pdm run mypy src/

# Run standalone demo
pdm run python -m textual_cmdorc.simple_app

# Or use the CLI
pdm run cmdorc-tui --config=config.toml

# Build for distribution
pdm build
```

## Code Architecture at a Glance

The codebase uses a **simplified flat list design** after removing the hierarchical tree complexity. The architecture has two main layers:

### Layer 1: Non-Textual Backend (`src/cmdorc_frontend/`)
Reusable orchestration logic decoupled from any UI framework:
- **orchestrator_adapter.py** - `OrchestratorAdapter`: Framework-agnostic wrapper for cmdorc's CommandOrchestrator
- **config.py** - Parse TOML configs, build command hierarchy, validate keyboard shortcuts
- **models.py** - Core dataclasses (CommandNode, TriggerSource, KeyboardConfig, etc.)
- **file_watcher.py** - `FileWatcherManager`: Watchdog integration for file-triggered commands
- **state_manager.py** - StateReconciler (sync UI with cmdorc state on startup)
- **watchers.py** - Abstract protocol for trigger sources
- **notifier.py** - Protocol for pluggable notifications

**Key Principle:** This layer is 100% non-Textual. It can be used in headless scenarios or embedded in other UIs.

### Layer 2: Textual TUI (`src/textual_cmdorc/`)
Simple flat list UI:
- **simple_app.py** - `SimpleApp`: All-in-one TUI shell using FileLinkList + CommandLink widgets
- **cli.py** - Command-line interface with auto-config generation

**Key Difference from Old Design:** No separate Controller/View split. SimpleApp directly uses OrchestratorAdapter and handles all UI concerns. For advanced embedding, use OrchestratorAdapter directly.

## Key Design Decisions

### Flat List Instead of Tree
Commands appear in TOML order as a simple list (not hierarchical tree):
- **Simpler mental model** - Command order matches TOML file
- **Less code** - Reduced from ~2000 lines to ~500 lines
- **Easier maintenance** - No tree reconciliation, cycle detection, or duplicate handling
- **Still functional** - Trigger chains work via cmdorc, tooltips show relationships

### SimpleApp for Standalone, OrchestratorAdapter for Embedding
- **SimpleApp** - All-in-one TUI shell for standalone use (90% of use cases)
- **OrchestratorAdapter** - Framework-agnostic backend for headless or custom UI scenarios

### cmdorc is the Source of Truth
- All state (running commands, history, trigger chains) lives in `CommandOrchestrator` from cmdorc
- TUI is a **viewer/controller** only—no hidden mutations or side effects
- Updates are driven by explicit callbacks, never by polling

### Sync-Safe Command Control
- UI callbacks (button clicks, keyboard input) use `request_run(name)` / `request_cancel(name)` (sync-safe)
- These methods schedule async tasks on the stored event loop
- Pure async methods (`run_command()`, `cancel_command()`) are available for async contexts

## High-Level Data Flow

### Startup
```
SimpleApp.__init__(config_path)
  → compose()
    → OrchestratorAdapter.__init__(config_path)
      → load_config() → CommandOrchestrator
      → load_frontend_config() → keyboard_config, watchers
    → FileLinkList() (empty, populated in on_mount)

  → on_mount()
    → adapter.attach(loop) → Start file watchers
    → Populate FileLinkList with CommandLink widgets (TOML order)
    → Wire lifecycle callbacks (success/failed/cancelled)
    → Bind global keyboard shortcuts
```

### Command Execution Flow
```
User clicks Play or presses [1]
  → SimpleApp._start_command(name)
  → adapter.request_run(name)
  → orchestrator.run_command(name)
  → Lifecycle callbacks fire:
    → _on_command_started() → Update UI to ⏳
    → _on_command_success/failed/cancelled() → Update UI to ✅/❌/⚠️
```

### Tooltip States
When a command runs, tooltips show different information based on state:

**Idle:** `Triggers: py_file_changed, manual\n[1] to run`

**Running:** `Stop — Ran automatically (file change)\npy_file_changed\n[1] to stop`

**Result:** `Last run: py_file_changed (✅ 2s ago)\nDuration: 1.5s\n[1] to run again`

Logic is in `SimpleApp._build_idle_tooltip()`, `_build_running_tooltip()`, `_build_result_tooltip()` and `TriggerSource` model methods.

## Configuration Extensions

textual-cmdorc extends cmdorc's TOML format with optional keyboard shortcuts and file watchers:

### Keyboard Shortcuts (Optional)
```toml
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3" }
enabled = true                    # default true
show_in_tooltips = true          # default true
```

**Validation:** Keys must be 1-9, a-z, or f1-f12. Invalid keys logged at startup.

### File Watchers (Optional, Repeating)
```toml
[[file_watcher]]
dir = "./src"
patterns = ["**/*.py"]           # optional, takes precedence
extensions = [".py"]             # optional, fallback
ignore_dirs = ["__pycache__"]    # optional
trigger = "py_file_changed"      # required — cmdorc event name
debounce_ms = 300                # optional, default 300ms
```

Watchers are loaded by `load_frontend_config()` and managed by `FileWatcherManager`.

## Testing Strategy

Current: **59 tests, 29% coverage** (simplified codebase)

### Test Organization
- **tests/conftest.py** - Fixtures (mock orchestrator, adapter, app)
- **tests/test_cli.py** - CLI argument parsing and config generation
- **tests/test_models.py** - Config parsing, TriggerSource, KeyboardConfig

### Running Tests
```bash
# Full test suite with coverage report
pdm run pytest --cov

# Run specific test marker
pdm run pytest -m integration

# Run single test with output
pdm run pytest tests/test_cli.py::test_parse_args_default -v -s

# Generate HTML coverage report
pdm run pytest --cov --cov-report=html
# Open htmlcov/index.html
```

## Important Files & Their Roles

| File | Purpose | Key Classes |
|------|---------|-------------|
| **src/textual_cmdorc/simple_app.py** | Standalone TUI shell | `SimpleApp`, `HelpScreen` |
| **src/cmdorc_frontend/orchestrator_adapter.py** | Framework-agnostic backend | `OrchestratorAdapter` |
| **src/cmdorc_frontend/config.py** | Parse TOML, build hierarchy | `load_frontend_config()` |
| **src/cmdorc_frontend/models.py** | Core dataclasses | `CommandNode`, `TriggerSource`, `KeyboardConfig` |
| **src/cmdorc_frontend/file_watcher.py** | Watchdog integration | `FileWatcherManager` |
| **src/textual_cmdorc/cli.py** | Command-line interface | `main()`, `create_default_config()` |
| **architecture.md** | Full design reference | Simplified design decisions |
| **README.md** | User-facing quickstart | Features, API, examples |

## Common Patterns & Anti-Patterns

### ✓ Correct Patterns

```python
# Standalone mode
from textual_cmdorc import SimpleApp
app = SimpleApp(config_path="config.toml")
app.run()

# Embedding SimpleApp in host app
from textual.app import App, ComposeResult
from textual_cmdorc import SimpleApp
class MyApp(App):
    def compose(self):
        self.cmdorc = SimpleApp.__new__(SimpleApp)
        self.cmdorc.__init__(config_path="config.toml")
        with Vertical():
            yield self.cmdorc.file_list  # Just the list widget

    async def on_mount(self):
        await self.cmdorc.on_mount()

    async def on_unmount(self):
        await self.cmdorc.on_unmount()

# Headless command execution (no UI) using OrchestratorAdapter
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter
adapter = OrchestratorAdapter(config_path="config.toml")
loop = asyncio.get_running_loop()
adapter.attach(loop)

# Wire callbacks
adapter.on_command_success("Build", lambda h: print("Build passed!"))
adapter.on_command_failed("Build", lambda h: print("Build failed!"))

# Execute
await adapter.run_command("Build")
adapter.detach()

# Sync-safe command execution from UI callbacks
def on_button_clicked(self):
    self.adapter.request_run("CommandName")  # Safe from UI context
```

### ✗ Anti-Patterns to Avoid

```python
# Wrong: Attach outside of async context
def compose(self):
    self.adapter.attach(loop)  # Loop not running yet!

# Wrong: Use async run_command() from sync callback
def on_button_clicked(self):
    asyncio.create_task(self.adapter.run_command("Cmd"))  # Unsafe

# Wrong: Poll orchestrator state
while True:
    state = adapter.orchestrator.get_state()
    # ...

# Wrong: Reference old CmdorcController or CmdorcView classes
from textual_cmdorc import CmdorcController  # Doesn't exist anymore!
```

## Invariants & Guarantees

1. **cmdorc is Source of Truth** - TUI never infers command state. Only reflects transitions reported by cmdorc callbacks.

2. **No Polling** - All updates driven by explicit callbacks from orchestrator.

3. **TOML Order Preserved** - Commands displayed in config appearance order.

4. **Trigger Chains Immutable** - Once captured in `RunHandle.trigger_chain` from cmdorc, chains are read-only.

5. **Callback Safety** - All outbound callbacks catch exceptions internally and log them. Exceptions do not propagate to caller.

6. **Thread-Safe Watchers** - File watcher callbacks use `call_soon_threadsafe()` to schedule async tasks from background threads.

7. **Idempotent Attach** - Calling `attach()` multiple times logs warning but is safe.

## External Dependencies

- **cmdorc** (0.3.0+) - Core orchestration engine (source of truth for state)
- **textual** (6.6.0+) - TUI framework (App, widgets, styling)
- **textual-filelink** (0.4.1+) - CommandLink widget with play/stop/settings buttons
- **watchdog** (4.0.0+) - File system event monitoring

## Key Gotchas

1. **Loop Must Be Running** - `adapter.attach(loop)` will fail if loop is not running. Always call in `on_mount()`.

2. **Trigger Chains Are Immutable** - Once captured in `RunHandle.trigger_chain`, chains are read-only. New chains only appear on next run.

3. **File Watcher Debouncing** - Events are debounced at 300ms (configurable). Rapid file changes coalesce into single trigger.

4. **Config Reload Drops History** - `action_reload_config()` rebuilds entire list and loses command history (no persistence yet).

5. **No Hierarchical Display** - Old tree-based design removed. Commands shown in flat list only. Hierarchy still built in backend for future use.

## Architecture Evolution

This project underwent a major simplification (v0.2.0):

### Removed Features
- ❌ Hierarchical tree display (now flat list)
- ❌ CmdorcController + CmdorcView split (now SimpleApp + OrchestratorAdapter)
- ❌ CmdorcCommandLink wrapper (use textual-filelink's CommandLink directly)
- ❌ Duplicate command tracking (not needed in flat list)
- ❌ Phase-based test files (simplified to test_cli.py, test_models.py)
- ❌ Log pane (may add later)
- ❌ State reconciliation on mount (no persistence yet)

### Kept Features
- ✅ OrchestratorAdapter (reusable backend)
- ✅ Config parsing with keyboard + watchers
- ✅ TriggerSource model (semantic summaries, chain formatting)
- ✅ CommandNode hierarchy (built but not displayed, for future frontends)
- ✅ File watching via watchdog
- ✅ Keyboard shortcuts
- ✅ Help screen

See **architecture.md** for full design rationale.

## Documentation Files

- **architecture.md** - Authoritative design reference (simplified v0.2.0)
- **README.md** - User-facing quickstart and feature overview
- **EMBEDDING.md** - Embedding guide (may be outdated, refer to SimpleApp docstring)
- **implementation.md** - Phase-by-phase implementation guide (historical)
- **plan.md** - Project roadmap (historical)
- **CHANGELOG.md** - Version history and breaking changes

## When in Doubt

1. **Architecture questions** → See `architecture.md` (simplified design)
2. **Standalone usage** → See `SimpleApp` in `simple_app.py`
3. **Embedding/headless usage** → See `OrchestratorAdapter` in `orchestrator_adapter.py`
4. **Config format** → See README.md or sample configs
5. **Test coverage** → Run `pdm run pytest --cov` to see what's missing
