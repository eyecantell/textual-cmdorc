# textual-cmdorc: "Coming Soon" TUI Frontend for cmdorc Command Orchestration

[![CI](https://github.com/eyecantell/textual-cmdorc/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/textual-cmdorc/actions)
[![PyPI](https://img.shields.io/pypi/v/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![Python Versions](https://img.shields.io/pypi/pyversions/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![License](https://img.shields.io/pypi/l/textual-cmdorc.svg)](https://github.com/eyecantell/textual-cmdorc/blob/main/LICENSE)

A Textual-based TUI wrapper for [cmdorc](https://github.com/eyecantell/cmdorc), displaying hierarchical command workflows with real-time status updates, manual controls, and trigger inputs. Ideal for developer tools, automation monitoring, or interactive workflows.

The project is structured with a shared backend (`cmdorc_frontend`) for config parsing, models, state management, and abstract watchers—enabling easy extension to other frontends (e.g., VSCode)—and TUI-specific code in `textual_cmdorc`.

## Features
- 📂 Load cmdorc TOML configs (e.g., config.toml) for dynamic command lists.
- 🌳 Hierarchical display: Indents chained commands based on lifecycle triggers (success/failed/cancelled) using Textual Tree for interactivity and collapsibility.
- 🔄 Real-time status: Spinners, icons (e.g., ✅/❌), and tooltips with full trigger chain breadcrumbs (e.g., "py_file_changed → command_success:Lint → command_success:Format").
- ⌨️ **Global keyboard shortcuts**: Configurable hotkeys (1-9 by default) to play/stop commands from anywhere in the app. Defined in `[keyboard]` section of TOML config.
- 🖱️ Interactive: Play/stop buttons for manual runs/cancels; input for triggers; app-level shortcuts (e.g., r to reload, Ctrl+C to cancel all).
- 📜 Log pane: Event/output snippets with toggle visibility.
- 🔧 File watching: Trigger events on file changes via watchdog (configurable in TOML).
- 🔄 State reconciliation: Syncs UI with cmdorc state on startup/reload.
- 🔍 Duplicate handling: Visual indicators for commands in multiple workflows.
- 💡 Smart tooltips: Show trigger chains, keyboard shortcuts, and helpful configuration hints for unconfigured commands.

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