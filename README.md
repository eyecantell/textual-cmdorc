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
- 🔄 Real-time status: Spinners, icons (e.g., ✅/❌), and tooltips with trigger context (e.g., "Running because: py_file_changed (file)").
- 🖱️ Interactive: Play/stop buttons for manual runs/cancels; input for triggers; keyboard shortcuts (e.g., r to reload, Ctrl+C to cancel all).
- 📜 Log pane: Event/output snippets with toggle visibility.
- 🔧 File watching: Trigger events on file changes via watchdog (configurable in TOML).
- 🔄 State reconciliation: Syncs UI with cmdorc state on startup/reload.
- 🔍 Duplicate handling: Visual indicators for commands in multiple workflows.

## Installation
```bash
pip install textual-cmdorc
```
Or with PDM:
```bash
pdm add textual-cmdorc
```

Requires Python 3.10+.

## Quick Start
1. Prepare a cmdorc config (e.g., examples/config.toml).
2. Run the TUI:
   ```bash
   textual run textual_cmdorc.app --config=examples/config.toml
   ```
   - Or programmatically:
     ```python
     from textual_cmdorc import CmdorcApp
     app = CmdorcApp(config_path="config.toml")
     app.run()
     ```

Example: Trigger "py_file_changed" via input → Watch Lint → Format → Tests chain with statuses/tooltips.

## Development
- Setup: `pdm install -G test`
- Tests: `pdm run pytest --cov` (90%+ coverage)
- Lint: `pdm run ruff check .`
- Docs: See implementation.md for detailed plan and tc_architecture.md for design.

## Contributing
Fork, branch (e.g., feature/new-tooltip), PR. Maintain 90% coverage.

## License
MIT - See [LICENSE](LICENSE).

## Links
- Repository: https://github.com/eyecantell/textual-cmdorc
- Issues: https://github.com/eyecantell/textual-cmdorc/issues
- Related: [cmdorc](https://github.com/eyecantell/cmdorc), [textual-filelink](https://github.com/eyecantell/textual-filelink)