# textual-cmdorc: "Coming Soon" TUI Frontend for cmdorc Command Orchestration

[![CI](https://github.com/eyecantell/textual-cmdorc/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/textual-cmdorc/actions)
[![PyPI](https://img.shields.io/pypi/v/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![Python Versions](https://img.shields.io/pypi/pyversions/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![License](https://img.shields.io/pypi/l/textual-cmdorc.svg)](https://github.com/eyecantell/textual-cmdorc/blob/main/LICENSE)

A Textual-based TUI wrapper for [cmdorc](https://github.com/eyecantell/cmdorc), displaying hierarchical command workflows with real-time status updates, manual controls, and trigger inputs.

**Key Design:** Embeddable by default. Use as a **standalone TUI app** or **embed in larger applications**. The architecture splits into non-Textual controller (orchestration) and passive Textual view (rendering), enabling reuse across frontends.

**Current Status:** ✅ All Phase 0-3 features complete and tested (137 tests, 47% coverage). Ready for production use.

**Ideal for:** Developer tools, automation monitoring, interactive workflows, or as a subcomponent in larger TUIs.

The project is structured with a shared backend (`cmdorc_frontend`) for config parsing, models, state management, and abstract watchers—enabling easy extension to other frontends (e.g., VSCode)—and TUI-specific code in `textual_cmdorc`.

## Features

### Core Functionality
- 📂 Load cmdorc TOML configs (e.g., config.toml) for dynamic command lists.
- 🌳 **Hierarchical display**: Indents chained commands based on lifecycle triggers (success/failed/cancelled) using Textual Tree for interactivity and collapsibility.
- 🔄 **Real-time status**: Spinners, icons (e.g., ✅/❌), and enhanced tooltips with full trigger chain breadcrumbs.
- 🖱️ **Interactive**: Play/stop buttons for manual runs/cancels; app-level shortcuts (e.g., r to reload, q to quit).
- 📜 **Log pane**: Event/output snippets with toggle visibility.
- 🔧 **File watching**: Trigger events on file changes via watchdog (configurable in TOML).

### UX Enhancements
- 💡 **Semantic Trigger Summaries**: Tooltips show human-readable summaries ("Ran automatically (file change)") before technical details, making it clear *why* commands ran.
- ⌨️ **Global Keyboard Shortcuts**: Configurable hotkeys (1-9 by default) to play/stop commands from anywhere. Defined in `[keyboard]` section of TOML. `[h]` shows help with all shortcuts and conflicts.
- ✅ **Startup Validation Summary**: Config issues (missing dirs, duplicate keys, unknown commands) displayed on app start in log pane—no hunting through logs.
- 🎯 **Duplicate Command Indicators**: Visual cues (↳ suffix) when commands appear in multiple workflows, with tooltip clarification.
- 🎨 **Smart Tooltips**: Show semantic summaries, full trigger chains, keyboard hints, and duplicate indicators all in one place.

### Embedding & Extensibility
- 🔗 **Embeddable Architecture**: Non-Textual controller + passive widget = reusable in larger TUIs or headless scenarios.
- 🔄 **State reconciliation**: Syncs UI with cmdorc state on startup/reload.
- 🎛️ **Pluggable notifications**: Custom logging/notification handlers via `CmdorcNotifier` protocol.

## Embedding textual-cmdorc in Larger Applications

textual-cmdorc can be used as a widget in any larger Textual app. Here's how:

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual_cmdorc import CmdorcController, CmdorcView

class MyLargerApp(App):
    """Example: Embed cmdorc command orchestration in a larger TUI."""

    def compose(self) -> ComposeResult:
        # Host app creates and owns the controller
        self.cmdorc = CmdorcController(
            "config.toml",
            enable_watchers=False  # Host controls watcher lifecycle
        )

        # Wire controller events to host app
        self.cmdorc.on_command_finished = self.on_cmdorc_done

        # CmdorcView is a passive widget—just include it in layout
        yield Horizontal(
            CmdorcView(self.cmdorc, show_log_pane=False),  # Embedded view
            MyOtherPanel(),
        )

    async def on_mount(self):
        # Host controls when to start watchers
        import asyncio
        loop = asyncio.get_running_loop()
        self.cmdorc.attach(loop)

    async def on_unmount(self):
        self.cmdorc.detach()

    def on_cmdorc_done(self, name: str, result):
        self.notify(f"Command finished: {name}")
```

See [architecture.md](architecture.md#65-embedding-architecture--contracts) for detailed embedding contracts and design details.

## Installation
```bash
pip install textual-cmdorc
```
Or with PDM:
```bash
pdm add textual-cmdorc
```

**Requirements:**
- Python 3.10+
- `watchdog` package (required for file watching features)

## Migration Guide (v0.1)

If you're upgrading to v0.1, the architecture has been redesigned to support embedding. Here's what changed:

### For Standalone Users (No Changes Required)
If you're only using `CmdorcApp` as a standalone TUI:
```python
from textual_cmdorc import CmdorcApp
app = CmdorcApp(config_path="config.toml")
app.run()
```
Everything works the same way. No changes needed!

### For Host Applications (New Embedding Support)
If you want to embed textual-cmdorc in a larger TUI:
```python
from textual_cmdorc import CmdorcController, CmdorcView
from textual.app import App

class MyLargerApp(App):
    def compose(self):
        # Create and own the controller
        self.cmdorc = CmdorcController("config.toml", enable_watchers=False)
        yield CmdorcView(self.cmdorc, show_log_pane=False)

    def on_mount(self):
        # Host controls when to attach to event loop
        import asyncio
        self.cmdorc.attach(asyncio.get_running_loop())
```

### What's New in v0.1
- **Embeddable Architecture**: Use as a widget in larger TUIs
- **Semantic Trigger Summaries**: Tooltips show "Ran automatically (file change)" before technical details
- **Startup Validation**: Config issues shown immediately on app start
- **Duplicate Indicators**: Visual (↳) suffix when commands appear multiple times
- **Help Screen**: Press `h` to see keyboard shortcuts and conflicts
- **Stable Public API**: Controller API frozen for v0.1, safe for embedding

See [architecture.md](architecture.md#65-embedding-architecture--contracts) for detailed embedding contracts.

## Quick Start
1. Initialize a config (optional):
   ```bash
   cmdorc init config.toml  # Generates config with keyboard shortcut placeholders
   ```
   Or prepare a cmdorc config manually (e.g., examples/config.toml) with optional `[keyboard]` section:
   ```toml
   [keyboard]
   shortcuts = { Lint = "1", Format = "2", Tests = "3" }
   enabled = true
   ```

2. Run the TUI:
   ```bash
   textual run textual_cmdorc.app --config=config.toml
   ```
   - Or programmatically:
     ```python
     from textual_cmdorc import CmdorcApp
     app = CmdorcApp(config_path="config.toml")
     app.run()
     ```

3. Use keyboard shortcuts (e.g., press `1` to run/stop Lint, `2` for Format) or click play/stop buttons.

Example: Save a .py file → Watch "py_file_changed" → Lint → Format → Tests chain. Tooltips show full trigger breadcrumbs. Press `3` anywhere to stop Tests.

## Development
- Setup: `pdm install -G test`
- Tests: `pdm run pytest --cov` (90%+ coverage)
- Lint: `pdm run ruff check .`
- Docs: See implementation.md for detailed plan and architecture.md for design.

## Contributing
Fork, branch (e.g., feature/new-tooltip), PR. Maintain 90% coverage.

## License
MIT - See [LICENSE](LICENSE).

## Links
- Repository: https://github.com/eyecantell/textual-cmdorc
- Issues: https://github.com/eyecantell/textual-cmdorc/issues
- Related: [cmdorc](https://github.com/eyecantell/cmdorc), [textual-filelink](https://github.com/eyecantell/textual-filelink)