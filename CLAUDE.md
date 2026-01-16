# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**textual-cmdorc** is an embeddable TUI frontend for [cmdorc](https://github.com/eyecantell/cmdorc) command orchestration. It displays commands in a flat list with real-time status updates, manual controls, and file watching.

- **Status:** Production ready
- **Python:** 3.10+
- **Core Dependencies:** Textual 6.6.0+, cmdorc 0.8.1+, watchdog 4.0.0+, textual-filelink 0.8.0+
- **Architecture:** Two-layer design with CmdorcWidget (embeddable) and CmdorcApp (standalone wrapper)

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

# Run standalone TUI
pdm run cmdorc-tui

# Or with config files (positional arguments)
pdm run cmdorc-tui dev.toml
pdm run cmdorc-tui dev.toml deploy.toml  # Multiple = switchable configs

# Or with --config flag
pdm run cmdorc-tui --config=config.toml

# Run with logging enabled
pdm run cmdorc-tui --log-file
pdm run cmdorc-tui --log-file --log-level INFO --log-all

# Build for distribution
pdm build
```

## Code Architecture at a Glance

The codebase uses a **simplified flat list design** after removing the hierarchical tree complexity. The architecture has two main layers:

### Layer 1: Non-Textual Backend (`src/cmdorc_frontend/`)
Reusable orchestration logic decoupled from any UI framework:
- **orchestrator_adapter.py** - `OrchestratorAdapter`: Framework-agnostic wrapper for cmdorc's CommandOrchestrator
- **config.py** - Parse TOML configs, build command hierarchy, validate keyboard shortcuts
- **models.py** - Core dataclasses (CommandNode, TriggerSource, KeyboardConfig, UserSettings, etc.)
- **multiconfig.py** - Multi-config support (`ConfigSet`, `NamedConfig`, `load_cmdorc_tui_toml()`)
- **config_discovery.py** - Config discovery logic (`discover_config()`, `resolve_startup_config()`)
- **file_watcher.py** - `FileWatcherManager`: Watchdog integration for file-triggered commands
- **state_manager.py** - StateReconciler (sync UI with cmdorc state on startup)
- **watchers.py** - Abstract protocol for trigger sources
- **notifier.py** - Protocol for pluggable notifications

**Key Principle:** This layer is 100% non-Textual. It can be used in headless scenarios or embedded in other UIs.

### Layer 2: Textual TUI (`src/textual_cmdorc/`)
Two-layer widget architecture for maximum flexibility:
- **cmdorc_app.py** - Contains both:
  - `CmdorcWidget`: Composable widget for embedding in multi-panel layouts
  - `CmdorcApp`: Thin standalone wrapper (adds Header/Footer to CmdorcWidget)
- **config_switcher.py** - `ConfigSwitcher`: Dropdown widget for switching between named configs
- **file_separator.py** - `FileSeparator`: Visual separator showing command source files
- **setup_screen.py** - `SetupScreen`: First-run setup modal for creating initial config
- **watcher_status_line.py** - `WatcherStatusLine`: Widget for toggling file watchers on/off
- **cli.py** - Command-line interface with config discovery and utility commands
- **logging.py** - Logging utilities for debugging (`setup_logging()`, `disable_logging()`, `get_log_file_path()`)
- **tooltip_builders.py** - `TooltipBuilder`: Constructs all tooltip content (status, play/stop, output)
- **formatting.py** - Pure utility functions for time formatting, ANSI stripping, output preview

**Key Design:** CmdorcWidget contains all orchestration logic and can be embedded anywhere. CmdorcApp wraps it for standalone use.

## Key Design Decisions

### Flat List Instead of Tree
Commands appear in TOML order as a simple list (not hierarchical tree):
- **Simpler mental model** - Command order matches TOML file
- **Less code** - Reduced from ~2000 lines to ~750 lines
- **Easier maintenance** - No tree reconciliation, cycle detection, or duplicate handling
- **Still functional** - Trigger chains work via cmdorc, tooltips show relationships

### CmdorcWidget + CmdorcApp Architecture
- **CmdorcWidget** - Composable widget for embedding (e.g., 3-column layouts)
- **CmdorcApp** - Standalone wrapper (adds Header/Footer)
- **OrchestratorAdapter** - Framework-agnostic backend for headless scenarios

This supports both standalone use (90% of cases) and clean embedding in larger TUIs.

### cmdorc is the Source of Truth
- All state (running commands, history, trigger chains) lives in `CommandOrchestrator` from cmdorc
- TUI is a **viewer/controller** only—no hidden mutations or side effects
- Updates are driven by explicit callbacks, never by polling

### Sync-Safe Command Control
- UI callbacks (button clicks, keyboard input) use `request_run(name)` / `request_cancel(name)` (sync-safe)
- These methods schedule async tasks on the stored event loop
- Pure async methods (`run_command()`, `cancel_command()`) are available for async contexts

### File Watcher Toggle Architecture
- **Lightweight toggle** - File watchers stay running, only trigger firing is toggled
- **`FileWatcherManager._enabled` flag** - Controls whether triggers fire
- **No observer restart** - Avoids heavyweight stop/start operations
- **UI components:**
  - `WatcherStatusLine` widget - Shows state and handles clicks
  - Appears above command list only if watchers configured
  - Keyboard shortcut 'w' to toggle
- **API methods:**
  - `adapter.enable_watchers()` - Enable trigger firing
  - `adapter.disable_watchers()` - Disable trigger firing
  - `adapter.are_watchers_enabled()` - Check state
- **Use case:** Disable triggers when making bulk file changes without triggering commands

### Multi-Config Support
Support for multiple named configurations via `cmdorc-tui.toml`:

**Config Discovery (priority order):**
1. `cmdorc-tui.toml` → Multi-config mode with named configs
2. `commands.toml` → Single-config mode (preferred)
3. `config.toml` → Single-config mode (legacy fallback)
4. None → Auto-create or show setup screen

**cmdorc-tui.toml format:**
```toml
# First config is the default
[[config]]
name = "Development"
files = ["./config.toml", "./build.toml", "./test.toml"]

[[config]]
name = "Build Only"
files = ["./build.toml"]
```

**UI Components:**
- `ConfigSwitcher` - Dropdown for switching configs (appears with 2+ configs)
- `FileSeparator` - Shows source file between commands from different files
- Ctrl+K keyboard shortcut for cycling configs

**CLI Commands:**
- `cmdorc-tui --list-configs` - List available named configs
- `cmdorc-tui --validate` - Validate cmdorc-tui.toml
- `cmdorc-tui --init-configs` - Auto-generate from existing TOML files
- `cmdorc-tui --config "Development"` - Start with named config
- `cmdorc-tui dev.toml` - Single config file (shows static label)
- `cmdorc-tui dev.toml deploy.toml` - Multiple config files (shows dropdown switcher)

**Settings Persistence:**
- Active config saved in `.cmdorc/settings.json`
- Restored on next startup

## High-Level Data Flow

### Startup
```
CmdorcApp.__init__(config_path)
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
  → CmdorcApp._start_command(name)
  → adapter.request_run(name)
  → orchestrator.run_command(name)
  → Lifecycle callbacks fire:
    → _on_command_started() → Update UI to ⏳
    → _on_command_success/failed/cancelled() → Update UI to ✅/❌/⚠️
```

### Tooltip Architecture
Commands have two separate tooltip systems for better UX:

**Status Icon Tooltips** (◯/⏳/✅/❌/⚠️) - Show trigger info and state:
- **Idle:** `Triggers: py_file_changed, manual\n[1] to run`
- **Running:** `Stop — Ran automatically (file change)\npy_file_changed\n[1] to stop`
- **Result:** `Last run: py_file_changed (✅ 2s ago)\nDuration: 1.5s\n[1] to run again`

**Play/Stop Button Tooltips** (▶️/⏹️) - Show resolved command:
- **Idle:** Shows command preview from `orchestrator.preview_command()` (e.g., `pytest ./tests -v`)
- **Running:** Shows resolved command being executed from `handle.resolved_command` (e.g., `Stop — pytest ./tests -v`)
- **Completed:** Restores to command preview

Logic is in:
- Status icon tooltips: `_build_idle_tooltip()`, `_build_running_tooltip()`, `_build_result_tooltip()`
- Play/Stop button tooltips: `_get_command_string()` uses `preview_command()`, updated via `set_status(run_tooltip=..., stop_tooltip=...)`
- Command name tooltip: Shows name with keyboard shortcuts (configured in CommandLink)

## Configuration Extensions

textual-cmdorc extends cmdorc's TOML format with optional keyboard shortcuts, editor configuration, and file watchers:

### Keyboard Shortcuts (Optional)
```toml
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3" }
enabled = true                    # default true
show_in_tooltips = true          # default true
```

**Validation:** Keys must be 1-9, a-z, or f1-f12. Invalid keys logged at startup.

### Editor Configuration (Optional)
```toml
[editor]
command_template = "code --goto {{ path }}:{{ line }}:{{ column }}"  # VSCode (default)
# command_template = "vim {{ line_plus }} {{ path }}"                # Vim
# command_template = "subl {{ path }}:{{ line }}:{{ column }}"       # Sublime Text
```

**Template Variables:** `{{ path }}`, `{{ line }}`, `{{ column }}`, `{{ line_plus }}`, `{{ line_colon }}`, `{{ path_relative }}`, `{{ path_name }}`

Configures which editor command is used when clicking file links (output files, config files). Defaults to VSCode if not specified.

### File Watchers (Optional, Repeating)
```toml
[[file_watcher]]
dir = "./src"
extensions = [".py"]             # optional — file extensions to watch
recursive = true                 # optional, default true — recursively watch subdirectories
ignore_dirs = ["__pycache__"]    # optional — directories to ignore
trigger_emitted = "py_file_changed"      # required — cmdorc event name
debounce_ms = 300                # optional, default 300ms
```

Watchers are loaded by `load_frontend_config()` and managed by `FileWatcherManager`.

## Logging

textual-cmdorc includes a comprehensive logging system that coordinates with cmdorc and textual-filelink logging.

### Design Principles
- **Silent by default**: NullHandler attached on import (library best practice)
- **File-only logging**: No console output to avoid interfering with TUI display
- **Opt-in via CLI**: Users must explicitly enable logging with `--log-file`
- **Multi-package coordination**: Can enable logging for cmdorc + textual-filelink + textual-cmdorc together

### CLI Flags
```bash
cmdorc-tui                           # Silent (no logging)
cmdorc-tui --log-file                # Enable file logging (DEBUG level)
cmdorc-tui --log-file --log-level INFO   # File logging at INFO level
cmdorc-tui --log-file --log-all      # Log all packages (cmdorc + textual-filelink)
cmdorc-tui -v                        # Alias for --log-file (backward compat)
```

### Programmatic API
```python
from textual_cmdorc import setup_logging, disable_logging, get_log_file_path

# Enable file logging for debugging
setup_logging()  # Defaults: DEBUG level, .cmdorc/logs/cmdorc-tui.log

# Configure with options
setup_logging(
    level="INFO",
    log_dir=".cmdorc/logs",
    log_filename="my-app.log",
    log_all=True,  # Also log cmdorc + textual-filelink
)

# Disable all logging (useful for tests)
disable_logging()

# Get log file path
log_path = get_log_file_path()  # Returns Path object
```

### Logger Namespaces
- `textual_cmdorc.*` - TUI layer (CmdorcApp, CmdorcWidget, CLI)
- `cmdorc_frontend.*` - Backend layer (OrchestratorAdapter, FileWatcherManager, config)
- Both namespaces configured together by `setup_logging()`
- Set `propagate=False` to prevent duplicate logging to root

### Log Format
**Detailed** (default):
```
2026-01-05 10:23:45 | DEBUG    | cmdorc_frontend.file_watcher:45 | File event detected: modified src/app.py
```

**Simple**:
```
INFO:textual_cmdorc.orchestrator:Command started: Lint
```

### Log Rotation
- **Max file size**: 10MB (configurable via `max_bytes`)
- **Backup count**: 5 files (configurable via `backup_count`)
- **Default location**: `.cmdorc/logs/cmdorc-tui.log`

### When Embedding CmdorcWidget
Enable logging before creating widgets:
```python
from textual_cmdorc import setup_logging, CmdorcWidget

setup_logging()  # Enable before widget creation
widget = CmdorcWidget("config.toml")
```

Or use your app's existing logging configuration (textual-cmdorc loggers will propagate):
```python
import logging
logging.basicConfig(level=logging.DEBUG)  # Standard Python logging
```

## Testing Strategy

Current: **200 tests, 75% coverage** (includes command details modal, logging, and watcher toggle)

### Test Organization
- **tests/conftest.py** - Fixtures (mock orchestrator, adapter, app)
- **tests/test_cli.py** - CLI argument parsing, config generation, and logging flags
- **tests/test_cmdorc_app.py** - CmdorcWidget lifecycle and callbacks
- **tests/test_details_screen.py** - CommandDetailsScreen content builders and actions
- **tests/test_formatting.py** - Formatting utilities (time, output preview, ANSI)
- **tests/test_logging.py** - Logging utilities (setup, disable, file creation, rotation)
- **tests/test_models.py** - Config parsing, TriggerSource, KeyboardConfig
- **tests/test_tooltip_builders.py** - Tooltip content builders
- **tests/test_watcher_status_line.py** - WatcherStatusLine widget (7 tests, 100% coverage)

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
| **src/textual_cmdorc/cmdorc_app.py** | Widget + App architecture | `CmdorcWidget`, `CmdorcApp`, `HelpScreen` |
| **src/textual_cmdorc/config_switcher.py** | Config switcher widget | `ConfigSwitcher` |
| **src/textual_cmdorc/file_separator.py** | File separator widget | `FileSeparator` |
| **src/textual_cmdorc/setup_screen.py** | First-run setup modal | `SetupScreen` |
| **src/textual_cmdorc/watcher_status_line.py** | File watcher toggle widget | `WatcherStatusLine` |
| **src/textual_cmdorc/details_screen.py** | Command details modal | `CommandDetailsScreen` |
| **src/textual_cmdorc/logging.py** | Logging utilities | `setup_logging()`, `disable_logging()`, `get_log_file_path()` |
| **src/textual_cmdorc/tooltip_builders.py** | Tooltip content builders | `TooltipBuilder` |
| **src/textual_cmdorc/formatting.py** | Formatting utilities | `format_elapsed_time()`, `get_output_preview()` |
| **src/cmdorc_frontend/orchestrator_adapter.py** | Framework-agnostic backend | `OrchestratorAdapter` |
| **src/cmdorc_frontend/config.py** | Parse TOML, build hierarchy | `load_frontend_config()` |
| **src/cmdorc_frontend/models.py** | Core dataclasses | `CommandNode`, `TriggerSource`, `KeyboardConfig`, `UserSettings` |
| **src/cmdorc_frontend/multiconfig.py** | Multi-config support | `ConfigSet`, `NamedConfig`, `load_cmdorc_tui_toml()` |
| **src/cmdorc_frontend/config_discovery.py** | Config discovery | `discover_config()`, `resolve_startup_config()` |
| **src/cmdorc_frontend/file_watcher.py** | Watchdog integration | `FileWatcherManager` (with enable/disable) |
| **src/textual_cmdorc/cli.py** | Command-line interface | `main()`, `handle_list_configs()`, `handle_validate()` |
| **tests/test_multiconfig.py** | Multi-config tests | 45 tests |
| **tests/test_config_discovery.py** | Config discovery tests | 23 tests |
| **tests/test_config_switcher.py** | Config switcher tests | 18 tests |
| **tests/test_setup_screen.py** | Setup screen tests | 9 tests |
| **architecture.md** | Full design reference | Simplified design decisions |
| **README.md** | User-facing quickstart | Features, API, examples |

## Common Patterns & Anti-Patterns

### ✓ Correct Patterns

```python
# Standalone mode
from textual_cmdorc import CmdorcApp
app = CmdorcApp(config_path="config.toml")
app.run()

# Embedding in 3-column layout (new clean approach)
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual_cmdorc import CmdorcWidget

class My3ColumnApp(App):
    def compose(self):
        with Horizontal():
            yield LeftPanel()
            yield CmdorcWidget("config.toml")  # Clean embedding!
            yield RightPanel()

# Headless command execution (no UI) using OrchestratorAdapter
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter
adapter = OrchestratorAdapter(config_path="config.toml")
loop = asyncio.get_running_loop()
adapter.attach(loop)
# Sync-safe command execution from UI callbacks
def on_button_clicked(self):
    self.adapter.request_run("CommandName")  # Safe from UI context

# Enable logging before creating widgets
from textual_cmdorc import setup_logging, CmdorcWidget
setup_logging()  # Enable debugging logs
widget = CmdorcWidget("config.toml")

# Disable logging for tests
from textual_cmdorc import disable_logging
disable_logging()  # Silent operation

# Toggle file watchers programmatically
adapter.disable_watchers()  # Disable triggers (watchers still run)
adapter.enable_watchers()   # Re-enable triggers
if adapter.are_watchers_enabled():
    print("Watchers are enabled")
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

- **cmdorc** (0.9.0+) - Core orchestration engine (source of truth for state)
  - 0.8.1+ required for correct history ordering (most recent first)
  - 0.9.0+ includes logging support (`setup_logging()`, `disable_logging()`)
- **textual** (6.6.0+) - TUI framework (App, widgets, styling)
- **textual-filelink** (0.9.0+) - CommandLink widget with play/stop/settings buttons and tooltip support
  - 0.9.0+ includes logging support
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
- ❌ CmdorcController + CmdorcView split (now CmdorcApp + OrchestratorAdapter)
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
- **EMBEDDING.md** - Embedding guide (may be outdated, refer to CmdorcApp docstring)
- **implementation.md** - Phase-by-phase implementation guide (historical)
- **plan.md** - Project roadmap (historical)
- **CHANGELOG.md** - Version history and breaking changes

## When in Doubt

1. **Architecture questions** → See `architecture.md` (simplified design)
2. **Standalone usage** → See `CmdorcApp` and `CmdorcWidget` in `cmdorc_app.py`
3. **Embedding/headless usage** → See `OrchestratorAdapter` in `orchestrator_adapter.py`
4. **Config format** → See README.md or sample configs
5. **Test coverage** → Run `pdm run pytest --cov` to see what's missing
