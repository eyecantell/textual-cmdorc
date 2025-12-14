# textual-cmdorc: TUI Frontend for cmdorc Command Orchestration

[![CI](https://github.com/eyecantell/textual-cmdorc/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/textual-cmdorc/actions)
[![PyPI](https://img.shields.io/pypi/v/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![Python Versions](https://img.shields.io/pypi/pyversions/textual-cmdorc.svg)](https://pypi.org/project/textual-cmdorc/)
[![License](https://img.shields.io/pypi/l/textual-cmdorc.svg)](https://github.com/eyecantell/textual-cmdorc/blob/main/LICENSE)

A Textual-based TUI wrapper for [cmdorc](https://github.com/eyecantell/cmdorc), displaying hierarchical command workflows with real-time status updates, manual controls, and trigger inputs. Ideal for developer tools, automation monitoring, or interactive workflows.

## Features
- 📂 Load cmdorc TOML configs (e.g., config.toml) for dynamic command lists.
- 🌳 Hierarchical display: Indents chained commands based on lifecycle triggers (success/failed/cancelled).
- 🔄 Real-time status: Spinners, icons (e.g., ✅/❌), and tooltips with trigger context.
- 🖱️ Interactive: Play/stop buttons for manual runs/cancels; input for triggers.
- 📜 Log pane: Event/output snippets.
- 🔧 Tooltips: Show current trigger (e.g., "Running due to: manual") or possible triggers.

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
   - Or programmatically: See app.py for CmdorcApp usage.

Example: Trigger "py_file_changed" via input → Watch Lint → Format → Tests chain with statuses/tooltips.

## Development
- Setup: `pdm install -G test`
- Tests: `pdm run pytest --cov` (90%+ coverage)
- Lint: `pdm run ruff check .`
- Docs: See implementation.md for detailed plan.

## Contributing
Fork, branch (e.g., feature/new-tooltip), PR. Maintain 90% coverage.

## License
MIT - See [LICENSE](LICENSE).

## Links
- Repository: https://github.com/eyecantell/textual-cmdorc
- Issues: https://github.com/eyecantell/textual-cmdorc/issues
- Related: [cmdorc](https://github.com/eyecantell/cmdorc), [textual-filelink](https://github.com/eyecantell/textual-filelink)
```

**Rationale for Skeleton:** Mirrors textual-filelink's README (badges, sections) for consistency. Includes plan elements (hierarchy, tooltips) without spoilers. Prudent: Short, actionable; expand with examples/screenshots later.

This covers all points—next, implement the plan with these enhancements for a polished MVP. If we need external info (e.g., latest Textual versions), I can tool it, but we're good here.