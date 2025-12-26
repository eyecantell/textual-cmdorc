# textual-cmdorc: TUI Frontend for cmdorc Command Orchestration

[![CI](https://github.com/eyecantell/textual-cmdorc/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/textual-cmdorc/actions)
[![PyPI](https://img.shields.io/pypi/v/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![Python Versions](https://img.shields.io/pypi/pyversions/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![License](https://img.shields.io/pypi/l/textual-cmdorc.svg)](https://github.com/eyecantell/textual-cmdorc/blob/main/LICENSE)

A simple, embeddable TUI frontend for [cmdorc](https://github.com/eyecantell/cmdorc), displaying commands in a flat list with real-time status updates, manual controls, and file watching.

**Key Design:** Direct and simple. A single `SimpleApp` class wraps cmdorc's `CommandOrchestrator` with a flat list UI powered by [textual-filelink](https://github.com/eyecantell/textual-filelink).

**Current Status:** ✅ Production ready (59 tests, 29% coverage). ~500 lines of code.

**Ideal for:** Developer tools, automation monitoring, CI/CD interfaces, or as a subcomponent in larger TUIs.

## Features

### Core Functionality
- 📂 **TOML Configuration**: Load cmdorc configs (e.g., config.toml) for dynamic command lists
- 📋 **Flat List Display**: Commands shown in TOML order using textual-filelink's CommandLink widgets
- 🔄 **Real-time Status**: Icons (◯/⏳/✅/❌) and dynamic tooltips showing command state
- 🖱️ **Interactive Controls**: Play/stop buttons for manual command execution
- 🔧 **File Watching**: Auto-trigger commands on file changes via watchdog (configurable in TOML)
- ⚡ **Trigger Chains**: Commands automatically trigger other commands based on success/failure

### UX Enhancements
- 💡 **Smart Tooltips**: Two tooltip systems for maximum clarity
  - **Status icons** (◯/⏳/✅/❌): Show trigger sources, keyboard hints, and last run details
  - **Play/Stop buttons** (▶️/⏹️): Display resolved command preview (e.g., `pytest ./tests -v`)
- ⌨️ **Global Keyboard Shortcuts**: Configurable hotkeys (1-9, a-z, f1-f12) to run/stop commands
- 🎯 **Help Screen**: Press `[h]` to see all keyboard shortcuts
- 🔄 **Live Reload**: Press `[r]` to reload configuration without restarting

### Embedding & Extensibility
- 🔗 **Embeddable**: Use OrchestratorAdapter directly for headless or custom UI scenarios
- 🎛️ **Framework Agnostic Backend**: OrchestratorAdapter has no Textual dependencies
- 📦 **Simple Integration**: Import SimpleApp and run with a config path

## Quick Start

### Standalone App
```bash
# Install
pip install textual-cmdorc

# Auto-generate config.toml and launch
cmdorc-tui

# Or use custom config
cmdorc-tui --config my-config.toml
```

### Programmatic Usage
```python
from textual_cmdorc import SimpleApp

app = SimpleApp(config_path="config.toml")
app.run()
```

### Embedding in Larger Applications

For most embedding scenarios, use **OrchestratorAdapter** directly to build custom UIs:

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual_filelink import CommandLink, FileLinkList
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter
import asyncio

class MyApp(App):
    """Custom TUI using OrchestratorAdapter."""

    def compose(self) -> ComposeResult:
        yield Header()

        # Create adapter (loads config, creates orchestrator)
        self.adapter = OrchestratorAdapter(config_path="config.toml")

        # Build your own UI with CommandLink widgets
        self.file_list = FileLinkList(show_toggles=False, show_remove=False)
        yield self.file_list

        yield Footer()

    async def on_mount(self):
        # Attach adapter to event loop
        loop = asyncio.get_running_loop()
        self.adapter.attach(loop)

        # Populate list with commands
        for cmd_name in self.adapter.get_command_names():
            link = CommandLink(
                name=cmd_name,
                output_path=None,
                initial_status_icon="◯",
                initial_status_tooltip=f"Run {cmd_name}"
            )
            self.file_list.add_item(link)

        # Wire callbacks (update UI on command events)
        for cmd_name in self.adapter.get_command_names():
            self.adapter.on_command_success(
                cmd_name,
                lambda h, name=cmd_name: self._on_success(name, h)
            )

    async def on_unmount(self):
        self.adapter.detach()

    def _on_success(self, name, handle):
        # Update UI when command succeeds
        # (implement your own UI update logic here)
        pass
```

For headless/programmatic use (no UI), see the **OrchestratorAdapter** API below.

## Configuration

textual-cmdorc extends cmdorc's TOML format with optional keyboard shortcuts and file watchers:

```toml
# Standard cmdorc config
[[command]]
name = "Lint"
command = "ruff check --fix ."
triggers = ["py_file_changed"]

[[command]]
name = "Format"
command = "ruff format ."
triggers = ["command_success:Lint"]

[[command]]
name = "Tests"
command = "pytest ."
triggers = ["command_success:Format"]

# Optional: Keyboard shortcuts
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3" }
enabled = true
show_in_tooltips = true

# Optional: File watchers
[[file_watcher]]
dir = "./src"
patterns = ["**/*.py"]
trigger = "py_file_changed"
debounce_ms = 300
ignore_dirs = ["__pycache__", ".git"]
```

Run `cmdorc-tui` without a config file to auto-generate a starter config.

## Architecture

### SimpleApp (TUI Shell)
A single Textual App class that:
1. Loads config and creates `OrchestratorAdapter`
2. Builds a `FileLinkList` with `CommandLink` widgets in TOML order
3. Wires lifecycle callbacks to update UI on command state changes
4. Handles keyboard shortcuts and global actions (help, reload, quit)

### OrchestratorAdapter (Framework-Agnostic Backend)
A non-Textual adapter that:
- Wraps cmdorc's `CommandOrchestrator` with a simpler API
- Manages file watchers and triggers
- Provides `request_run()` / `request_cancel()` for thread-safe command control
- Emits lifecycle callbacks: `on_command_success`, `on_command_failed`, `on_command_cancelled`
- No Textual dependencies—reusable in headless scenarios or other UI frameworks

## API Reference

### SimpleApp
```python
from textual_cmdorc import SimpleApp

app = SimpleApp(config_path="config.toml")
app.run()
```

**Key Methods:**
- `__init__(config_path: str)` - Initialize with TOML config path
- `compose()` - Build UI (called by Textual)
- `on_mount()` - Populate commands and wire callbacks (called by Textual)
- `action_toggle_command(cmd_name: str)` - Run/stop command (keyboard shortcuts)
- `action_reload_config()` - Reload config from disk
- `action_show_help()` - Show help screen with keyboard shortcuts

### OrchestratorAdapter

Use `OrchestratorAdapter` for headless scenarios or custom UI frameworks:

```python
import asyncio
from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter

async def main():
    # Create adapter (loads config, creates orchestrator)
    adapter = OrchestratorAdapter(config_path="config.toml")

    # Attach to event loop (starts file watchers)
    loop = asyncio.get_running_loop()
    adapter.attach(loop)

    # Register callbacks
    adapter.on_command_success("Tests", lambda h: print(f"✅ Tests passed in {h.duration_str}"))
    adapter.on_command_failed("Tests", lambda h: print(f"❌ Tests failed: {h.return_code}"))

    # Execute commands
    await adapter.run_command("Lint")  # Async execution
    adapter.request_run("Tests")  # Thread-safe (returns immediately)

    # Wait for commands to complete...
    await asyncio.sleep(5)

    # Cleanup
    adapter.detach()

asyncio.run(main())
```

**Key Methods:**
- `attach(loop: asyncio.AbstractEventLoop)` - Attach to event loop and start watchers
- `detach()` - Stop watchers and cleanup
- `request_run(name: str)` - Thread-safe command execution request
- `request_cancel(name: str)` - Thread-safe command cancellation request
- `run_command(name: str)` - Async command execution
- `cancel_command(name: str)` - Async command cancellation
- `get_command_names()` - Get all command names in TOML order
- `on_command_success(name: str, callback: Callable)` - Register success callback
- `on_command_failed(name: str, callback: Callable)` - Register failure callback
- `on_command_cancelled(name: str, callback: Callable)` - Register cancellation callback

## Development

```bash
# Setup
git clone https://github.com/eyecantell/textual-cmdorc.git
cd textual-cmdorc
pdm install -G test -G lint -G dev

# Run tests
pdm run pytest --cov

# Lint
pdm run ruff check .

# Format
pdm run ruff format .

# Run app
pdm run python -m textual_cmdorc.simple_app
```

## Architecture Decisions

### Why Flat List Instead of Tree?
The original design used a hierarchical tree to visualize trigger relationships. After extensive development (137 tests, ~2000 lines), we simplified to a flat list because:
1. **Simpler mental model**: Command order matches TOML file order
2. **Less code**: Reduced from ~2000 lines to ~500 lines
3. **Easier to maintain**: No tree reconciliation, cycle detection, or duplicate handling
4. **Still functional**: Trigger chains work via cmdorc, tooltips show relationships

### Why SimpleApp Instead of Controller+View Split?
The original embeddable architecture split concerns into `CmdorcController` (non-Textual) and `CmdorcView` (Textual widget). The new design simplifies to:
- **SimpleApp**: All-in-one TUI shell for standalone use
- **OrchestratorAdapter**: Framework-agnostic backend for advanced embedding

This is simpler for 90% of use cases while still supporting headless/custom UI scenarios via OrchestratorAdapter.

## Project Status

### Completed
- ✅ Flat list display with CommandLink widgets
- ✅ Real-time status updates (icons, tooltips)
- ✅ Keyboard shortcuts (configurable, conflict detection)
- ✅ File watchers (watchdog integration)
- ✅ Help screen (modal with shortcuts)
- ✅ Config reload (live without restart)
- ✅ CLI with auto-config generation
- ✅ 59 passing tests (29% coverage)

### Known Limitations
- No log pane (use terminal output instead)
- No hierarchical tree display
- Commands shown in TOML order only (no custom sorting)

## License

MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please:
1. Open an issue first for major changes
2. Follow existing code style (ruff format)
3. Add tests for new features
4. Update documentation

## Credits

- Built with [Textual](https://textual.textualize.io/)
- Uses [cmdorc](https://github.com/eyecantell/cmdorc) for command orchestration
- Uses [textual-filelink](https://github.com/eyecantell/textual-filelink) for command widgets
- File watching via [watchdog](https://github.com/gorakhargosh/watchdog)
