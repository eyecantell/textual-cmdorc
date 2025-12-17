# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**textual-cmdorc** is an embeddable TUI frontend for [cmdorc](https://github.com/eyecantell/cmdorc) command orchestration. It displays hierarchical command workflows with real-time status updates, manual controls, and trigger inputs.

- **Status:** Beta (v0.1.0) - Production ready with 137 tests, 47%+ coverage
- **Python:** 3.10+
- **Core Dependencies:** Textual 6.6.0+, cmdorc 0.2.1+, watchdog 4.0.0+

## Common Development Commands

```bash
# Setup development environment
pdm install -G test -G lint -G dev

# Run all tests with coverage
pdm run pytest --cov

# Run specific test file
pdm run pytest tests/test_controller.py -v

# Run single test
pdm run pytest tests/test_controller.py::test_name -v

# Lint code
pdm run ruff check .

# Format code
pdm run ruff format .

# Type checking
pdm run mypy src/

# Live development (watch mode for Textual)
pdm run textual-dev

# Run standalone demo
pdm run python -m textual_cmdorc.app --config=config.toml

# Build for distribution
pdm build
```

## Code Architecture at a Glance

The codebase is split into **three layers**, each serving a specific purpose:

### Layer 1: Non-Textual Backend (`src/cmdorc_frontend/`)
Reusable orchestration logic decoupled from any UI framework:
- **config.py** - Parse TOML configs, build command hierarchy, validate keyboard shortcuts
- **models.py** - Core dataclasses (CommandNode, TriggerSource, PresentationUpdate, etc.)
- **state_manager.py** - StateReconciler (sync UI with cmdorc state on startup)
- **watchers.py** - Abstract protocol for trigger sources (extensible for HTTP, Git hooks, etc.)
- **notifier.py** - Protocol for pluggable notifications (logging abstraction)

**Key Principle:** This layer is 100% non-Textual. It can be used in headless scenarios or embedded in other UIs.

### Layer 2: Textual-Specific Controller (`src/textual_cmdorc/controller.py`)
The **primary embedding point** for host applications:
- Owns `CommandOrchestrator` (from cmdorc), `FileWatcherManager`, and config state
- Provides lifecycle methods: `attach(loop)`, `detach()`
- Command control: `request_run(name)`, `request_cancel(name)` (sync-safe), and async versions
- Exposes keyboard metadata: `keyboard_hints`, `keyboard_conflicts`
- Emits callbacks: `on_command_started`, `on_command_finished`, `on_state_reconciled`, etc.
- Handles file watcher events and triggers via cmdorc

**Public API (v0.1 Stable):** All methods documented in class docstring marked "RECOMMENDATION #2"

### Layer 3: Textual Widgets (`src/textual_cmdorc/`)
UI rendering and interactivity:
- **view.py** - `CmdorcView`: Passive Textual widget, renders tree + log pane. No global key handling.
- **widgets.py** - `CmdorcCommandLink`: Extends cmdorc's `CommandLink` with trigger chains, tooltips, keyboard hints, duplicate indicators.
- **app.py** - `CmdorcApp`: Thin shell composing Controller + View for standalone mode only. Not suitable for embedding.
- **file_watcher.py** - `WatchdogWatcher`: Concrete watchdog implementation (abstract in backend).
- **integrator.py** - Wires controller callbacks to widgets, creates command trees.
- **keyboard_handler.py** - Helper for keyboard configuration and conflict detection.

## Key Design Decisions

### Embeddable by Default
The architecture enforces a clear separation:
- **Controller** (non-Textual) can be used independently or with any UI framework
- **View** (Textual widget) is passive—no global key bindings, pure rendering
- **App** (Textual app) is a thin shell for standalone mode; use Controller + View directly to embed

### cmdorc is the Source of Truth
- All state (running commands, history, trigger chains) lives in `CommandOrchestrator` from cmdorc
- TUI is a **viewer/controller** only—no hidden mutations or side effects
- Updates are driven by explicit callbacks, never by polling

### Sync-Safe Command Control
- UI callbacks (button clicks, keyboard input) use `request_run(name)` / `request_cancel(name)` (sync-safe)
- These methods schedule async tasks on the stored event loop
- Pure async methods (`run_command()`, `cancel_command()`) are available for async contexts

### File Watchers are Lifecycle-Controlled by Host
- `enable_watchers=False` for embedded mode (host controls when to start/stop)
- `enable_watchers=True` for standalone mode (auto-starts on `attach()`)
- Watcher callbacks use `call_soon_threadsafe()` for thread safety

## High-Level Data Flow

### Startup (Embedded Mode)
```
Host App compose()
  → Create CmdorcController(config_path, enable_watchers=False)
    → ConfigParser loads TOML (commands, keyboard shortcuts, watcher configs)
    → CommandOrchestrator initialized with commands
    → FileWatcherManager created (idle, not started yet)
  → Create CmdorcView(controller)
    → Integrator builds command tree, wires callbacks

Host App on_mount()
  → controller.attach(asyncio.get_running_loop())
    → FileWatcherManager starts observers
  → Optional: Wire controller callbacks to host events
  → Optional: Bind keyboard shortcuts from controller.keyboard_hints
```

### Command Execution Flow
```
User Action (click, keyboard, file change, or trigger)
  → CmdorcCommandLink or FileWatcherManager
  → controller.request_run(name) or _on_file_change(trigger)
  → CommandOrchestrator.run_command(name)
    → Emits lifecycle callbacks
    → Integrator receives callbacks
    → Updates CmdorcCommandLink display
    → View rerenders
```

### Trigger Chain Display
When a command runs, tooltips show (in order):
1. **Semantic Summary** - "Ran automatically (file change)" or "Ran manually"
2. **Full Trigger Chain** - "py_file_changed → command_success:Lint → ..." (left-truncated if too long)
3. **Keyboard Hint** - "[1] to stop" (if shortcut configured)
4. **Duplicate Indicator** - "(Appears in multiple workflows)" (if command in tree multiple times)

Logic is in `CmdorcCommandLink._update_tooltips()` and `TriggerSource` model methods.

## Configuration Extensions

textual-cmdorc extends cmdorc's TOML format with two optional sections:

### Keyboard Shortcuts (Optional)
```toml
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3", Build = "b" }
enabled = true                    # default true
show_in_tooltips = true          # default true
```

**Validation:** Keys must be 1-9, a-z, or f1-f12. Invalid keys logged at startup.

### File Watchers (Optional, Repeating)
```toml
[[file_watcher]]
dir = "./src"                    # required
patterns = ["**/*.py"]           # optional, takes precedence
extensions = [".py"]             # optional, fallback
ignore_dirs = ["__pycache__"]    # optional
trigger = "py_file_changed"      # required — cmdorc event name
debounce_ms = 300                # optional, default 300ms
```

Watchers are loaded by `ConfigParser.load_frontend_config()` and managed by `FileWatcherManager`.

## Testing Strategy

Target: **≥90% coverage** (CI fails below 90%)

### Test Organization
- **tests/conftest.py** - Fixtures (mock orchestrator, controller, app)
- **tests/test_controller.py** - CmdorcController lifecycle and command control
- **tests/test_models.py** - Config parsing, TriggerSource, PresentationUpdate
- **tests/test_phase*.py** - Integration tests (phases correspond to implementation phases)
- **tests/test_view.py** - CmdorcView rendering and widget updates

### Coverage by Module
| Module | Target | Notes |
|--------|--------|-------|
| config.py | 100% | Pure function, table-driven tests |
| file_watcher.py | 98% | Mock observer + asyncio sleep tests |
| integrator.py | 95% | Mock orchestrator, assert callbacks |
| widgets.py | 92% | Textual test utilities + reactive tests |
| app.py | 88%+ | Integration tests with mounted app |

### Running Tests
```bash
# Full test suite with coverage report
pdm run pytest --cov

# Run specific test marker
pdm run pytest -m integration

# Run single test with output
pdm run pytest tests/test_controller.py::test_attach_idempotent -v -s

# Generate HTML coverage report
pdm run pytest --cov --cov-report=html
# Open htmlcov/index.html
```

## Important Files & Their Roles

| File | Purpose | Key Classes |
|------|---------|-------------|
| **src/cmdorc_frontend/config.py** | Parse TOML, build hierarchy | `ConfigParser`, `load_frontend_config()` |
| **src/cmdorc_frontend/models.py** | Core dataclasses | `CommandNode`, `TriggerSource`, `PresentationUpdate`, `ConfigValidationResult` |
| **src/textual_cmdorc/controller.py** | Primary embed point | `CmdorcController` |
| **src/textual_cmdorc/view.py** | Textual widget | `CmdorcView` |
| **src/textual_cmdorc/widgets.py** | Command link with tooltips | `CmdorcCommandLink` |
| **src/textual_cmdorc/app.py** | Standalone app shell | `CmdorcApp`, `HelpScreen` |
| **src/textual_cmdorc/file_watcher.py** | Watchdog integration | `WatchdogWatcher`, `_DebouncedHandler` |
| **src/textual_cmdorc/integrator.py** | Wire callbacks | `create_command_link()` |
| **architecture.md** | Full design reference | All design decisions, contracts, invariants |
| **EMBEDDING.md** | How to embed in larger TUIs | Real-world examples, patterns, troubleshooting |

## Common Patterns & Anti-Patterns

### ✓ Correct Patterns

```python
# Standalone mode
from textual_cmdorc import CmdorcApp
app = CmdorcApp(config_path="config.toml")
app.run()

# Embedding in host app
from textual_cmdorc import CmdorcController, CmdorcView
class MyApp(App):
    def compose(self):
        self.cmdorc = CmdorcController("config.toml", enable_watchers=False)
        yield CmdorcView(self.cmdorc)

    async def on_mount(self):
        loop = asyncio.get_running_loop()
        self.cmdorc.attach(loop)  # Attach after compose

    async def on_unmount(self):
        self.cmdorc.detach()  # Always cleanup

# Headless command execution (no UI)
controller = CmdorcController("config.toml", enable_watchers=False)
loop = asyncio.get_running_loop()
controller.attach(loop)
await controller.run_command("Deploy")
controller.detach()

# Sync-safe command execution from UI callbacks
def on_button_clicked(self):
    self.controller.request_run("CommandName")  # Safe from UI context

# Check keyboard conflicts before binding
conflicts = controller.keyboard_conflicts
for key, cmd_name in controller.keyboard_hints.items():
    if key not in conflicts:
        app.bind(key, lambda n=cmd_name: controller.request_run(n))
```

### ✗ Anti-Patterns to Avoid

```python
# Wrong: Use enable_watchers=True in embedded mode
controller = CmdorcController(config_path, enable_watchers=True)

# Wrong: Attach outside of async context
def compose(self):
    self.controller.attach(loop)  # Loop not running yet!

# Wrong: Use async run_command() from sync callback
def on_button_clicked(self):
    asyncio.create_task(self.controller.run_command("Cmd"))  # Unsafe

# Wrong: Poll orchestrator state
while True:
    state = controller.orchestrator.get_state()
    # ...

# Wrong: Bind global keys inside controller
class CmdorcController:
    def attach(self, loop):
        app.bind("1", self.run_command)  # Controller shouldn't know about app!

# Wrong: Call app.exit() from controller
def on_command_done(self):
    app.exit()  # Controller must not depend on Textual
```

## Invariants & Guarantees

1. **State Reconciliation** - Runs once on mount after tree is built. Syncs UI with cmdorc state (handles case where cmdorc has running commands but TUI just started). Idempotent and read-only.

2. **No Inferred State** - TUI never infers command state. Only reflects transitions reported by cmdorc callbacks.

3. **Cycle Breaking** - Cycles in command triggers are detected and broken arbitrarily. Commands in cycles may not appear in all branches.

4. **Callback Safety** - All outbound callbacks catch exceptions internally and log them. Exceptions do not propagate to caller.

5. **Thread-Safe Watchers** - File watcher callbacks use `call_soon_threadsafe()` to schedule async tasks from background threads.

6. **Idempotent Attach** - Calling `attach()` multiple times is safe. Validates loop is running and guards against double-start.

## Phase-Based Implementation Reference

This project uses phase-based development (tracked in **implementation.md**):

- **Phase 0** - Embeddable architecture (Controller + View split)
- **Phase 1** - Config parsing & models (Keyboard + Watchers)
- **Phase 2** - Trigger chain display (Semantic summaries, truncation)
- **Phase 3** - Duplicate command indicators
- **Phase 4** - Keyboard shortcuts & conflicts
- **Phase 5** - Startup validation summary
- **Phase 6** - Help screen (ModalScreen, shortcuts, conflicts)
- **Phase 7** - Polish, testing, docs

Each phase has corresponding tests in `tests/test_phaseN*.py`.

## External Dependencies

- **cmdorc** (0.2.1+) - Core orchestration engine (source of truth for state)
- **textual** (6.6.0+) - TUI framework (Widgets, App, ModalScreen, Tree, Log, etc.)
- **watchdog** (4.0.0+) - File system event monitoring (pluggable for other backends)

## Key Gotchas

1. **Loop Must Be Running** - `controller.attach(loop)` will fail if loop is not running. Always call in `on_mount()`.

2. **Trigger Chains Are Immutable** - Once captured in `RunHandle.trigger_chain` from cmdorc, chains are read-only. New chains only appear on next run.

3. **Duplicate Command Tracking** - Each view independently tracks duplicates. Multiple views with same controller each maintain own `_command_links` dict.

4. **File Watcher Debouncing** - Events are debounced at 300ms (configurable). Rapid file changes coalesce into single trigger.

5. **Keyboard Conflicts** - Keys with multiple commands are flagged in `keyboard_conflicts`. Host app should check before binding globally.

## Documentation Files

- **architecture.md** - Authoritative design reference (67 sections, full contract documentation)
- **EMBEDDING.md** - Embedding guide with patterns, real-world scenarios, troubleshooting
- **implementation.md** - Phase-by-phase implementation guide (referenced in architecture)
- **plan.md** - Project roadmap and completed phases
- **RELEASE_CHECKLIST.md** - Pre-release validation steps
- **CHANGELOG.md** - Version history and breaking changes
- **README.md** - User-facing quickstart and feature overview

## When in Doubt

1. **Architecture questions** → See `architecture.md` (section numbers in code comments reference it)
2. **Embedding questions** → See `EMBEDDING.md` (patterns, real-world examples)
3. **Implementation questions** → Check corresponding phase in `implementation.md`
4. **API stability** → Check docstring in `CmdorcController` (marked "RECOMMENDATION #2")
5. **Test coverage** → Run `pdm run pytest --cov` to see what's missing
