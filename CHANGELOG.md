# Changelog

All notable changes to textual-cmdorc are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-17

### Added

#### Core Architecture & Features
- **Embeddable by design**: Split into non-Textual `CmdorcController` and passive `CmdorcView` widget
- **Standalone TUI app**: `CmdorcApp` thin shell for traditional usage
- **Real-time status**: Command status display with spinner, icons (✅/❌), and dynamic updates
- **Hierarchical display**: Tree widget showing command chains and dependencies
- **Keyboard shortcuts**: Global hotkeys (1-9, a-z, f1-f12) configurable via `[keyboard]` TOML section
- **Help screen**: Modal help with keyboard shortcuts, conflicts, and tips (press `h`)
- **Trigger chain display**: Breadcrumb trails showing full execution context
- **File watching**: watchdog integration with debouncing and pattern matching
- **Log pane**: Toggle-able event log with output snippets
- **Duplicate indicators**: Visual markers (↳) for commands appearing in multiple workflows

#### Critical Architectural Fixes (8 Fixes)

1. **FIX #1 - Sync-Safe Async API**: `request_run()` and `request_cancel()` use stored `_loop` reference for safe execution from UI callbacks
2. **FIX #2 - Duplicate Tracking**: `view._command_links` dict tracks all widget instances per command for duplicate detection
3. **FIX #3 - Keyboard Conflict Detection**: Cached `keyboard_conflicts` property identifies keys with multiple commands
4. **FIX #4 - Adapter Pattern**: Integrator module converts `RunHandle` to domain models, keeping them UI-agnostic
5. **FIX #5 - Thread-Safe Watchers**: File watcher callbacks use `loop.call_soon_threadsafe()` for asyncio safety
6. **FIX #6 - Help Screen with ModalScreen**: Replaced log pane with proper modal for help display
7. **FIX #7 - Tooltip Truncation**: Minimum width check (10 chars) prevents negative values in trigger chain formatting
8. **FIX #8 - Keyboard Validation**: Keys validated against `VALID_KEYS` set (1-9, a-z, f1-f12)

#### UX Enhancements

- **Semantic Trigger Summaries**: Tooltips show human-readable summaries ("Ran automatically (file change)") before technical details
- **Smart Tooltips**: Display semantic summary + full trigger chain + keyboard hint + duplicate indicator
- **Startup Validation Summary**: Configuration issues shown on app start (only if warnings/errors exist)
- **Keyboard Conflict Highlighting**: Help screen shows conflicting keys with resolution info
- **Duplicate Warning Messages**: Clear communication about commands appearing multiple times

#### Embedding Support

- **Three-layer architecture**: CmdorcApp → CmdorcView → CmdorcController (non-Textual)
- **Headless mode**: Use controller without UI for programmatic command execution
- **Multiple controllers**: Support for several independent workflows in one app
- **Event-driven architecture**: Callbacks for `on_command_started`, `on_command_finished`, `on_validation_result`, `on_state_reconciled`
- **Pluggable notifier**: Custom logging/notifications via `CmdorcNotifier` protocol
- **State reconciliation**: `StateReconciler` syncs UI with orchestrator on startup
- **Stable public API**: Controller API frozen for v0.1, documented contracts

#### Configuration

- **Keyboard section**: `[keyboard]` with `shortcuts` dict, `enabled` flag, and `show_in_tooltips` option
- **File watchers**: `[[file_watcher]]` sections with patterns, extensions, debouncing
- **Validation**: Config validation with warnings and errors reported at startup

#### Testing & Quality

- **157 comprehensive tests** covering all phases
- **48% code coverage** with 94% for critical keyboard handler
- **Unit, integration, and embedding tests**
- **Test infrastructure** with conftest.py mocks for cmdorc dependency
- **pytest-asyncio support** for async test cases

#### Documentation

- **architecture.md**: Complete design reference with contracts and guarantees
- **implementation.md**: Phase-by-phase implementation guide with 8 fixes documented
- **README.md**: Quick start, features, migration guide, and embedding instructions
- **EMBEDDING.md**: Comprehensive 50-page embedding guide with real-world scenarios
- **Example applications**:
  - `examples/embedding_dev_dashboard.py` - Multi-pipeline monitoring dashboard
  - `examples/embedding_headless.py` - Programmatic CI/CD execution patterns
- **Docstrings**: Comprehensive docstrings throughout codebase

### Technical Specifications

#### Modules

- `src/textual_cmdorc/app.py` - Standalone TUI app shell (309 lines)
- `src/textual_cmdorc/controller.py` - Non-Textual orchestration (256 lines)
- `src/textual_cmdorc/view.py` - Passive tree widget (125 lines)
- `src/textual_cmdorc/widgets.py` - Enhanced command link (165 lines)
- `src/textual_cmdorc/keyboard_handler.py` - Safe keyboard binding (115 lines)
- `src/textual_cmdorc/integrator.py` - Callback wiring (150 lines)
- `src/textual_cmdorc/file_watcher.py` - watchdog integration (41 lines)
- `src/cmdorc_frontend/models.py` - Data models (200+ lines)
- `src/cmdorc_frontend/config.py` - Config parsing (95 lines)
- `src/cmdorc_frontend/state_manager.py` - State reconciliation (100 lines)
- `src/cmdorc_frontend/watchers.py` - Watcher protocol (30 lines)
- `src/cmdorc_frontend/notifier.py` - Notification protocol (60 lines)

#### Dependencies

- **textual** ≥ 6.6.0
- **cmdorc** ≥ 0.1.0
- **watchdog** ≥ 4.0.0
- Python 3.10+

#### Test Suites

- `tests/test_controller.py` - 11 tests for controller lifecycle and API
- `tests/test_view.py` - 20 tests for tree rendering and duplicate tracking
- `tests/test_models.py` - 36 tests for data models and validation
- `tests/test_phase1_integration.py` - 19 tests for state management and integration
- `tests/test_phase2_keyboard.py` - 23 tests for keyboard handler and conflicts
- `tests/test_phase3_integration_full.py` - 25 tests for full feature integration
- `tests/test_phase5_embedding.py` - 20 tests for embedding patterns

### Known Limitations

- File watching patterns use watchdog's implementation (cross-platform but OS-dependent)
- Keyboard shortcuts limited to single-key combinations (no modifier combinations in v0.1)
- Tree rendering uses Textual's Tree widget (max nesting depends on terminal height)
- StateReconciler runs once on startup (not continuously)

### Breaking Changes

None - this is the initial v0.1.0 release.

### Migration Guide

For upgrading from pre-release versions:

1. Update imports: `from textual_cmdorc import CmdorcApp, CmdorcController, CmdorcView`
2. For standalone usage: No changes needed
3. For embedding: Use `CmdorcController(config, enable_watchers=False)` and wire callbacks
4. Add `[keyboard]` section to config for keyboard shortcuts (optional)
5. See EMBEDDING.md for detailed patterns

### Contributors

- **eyecantell** - Lead developer and architect

### Credits

- Built on [Textual](https://textual.textualize.io/) TUI framework
- Orchestration logic from [cmdorc](https://github.com/eyecantell/cmdorc)
- File watching via [watchdog](https://github.com/gorakhargosh/watchdog)

### Future Roadmap

#### v0.2.0 (Planned)
- Modifier key combinations (Ctrl+, Shift+, etc.)
- Keyboard shortcut customization at runtime
- Dark/light theme support
- Command search/filter interface
- Export command history to CSV/JSON
- Plugin system for custom widgets

#### v1.0.0 (Future)
- Remote command execution support
- WebSocket-based state sync
- Advanced scheduling (cron-like triggers)
- Performance optimizations for 1000+ commands
- Official plugin marketplace

---

## [Unreleased]

### Added
- **Command Preview Tooltips**: Play/stop buttons now show resolved commands using `orchestrator.preview_command()` and `handle.resolved_command`
  - Idle state: Play button displays command preview with variables resolved (e.g., `pytest ./tests -v`)
  - Running state: Stop button shows the actual command being executed
  - Completed state: Returns to command preview
  - Status icon tooltips unchanged (still show triggers, shortcuts, and last run info)
  - Requires textual-filelink 0.5.0+ for `run_tooltip`/`stop_tooltip` parameters

---

**Links:**
- [GitHub Repository](https://github.com/eyecantell/textual-cmdorc)
- [PyPI Package](https://pypi.org/project/textual-cmdorc/)
- [Textual Documentation](https://textual.textualize.io/)
- [cmdorc Documentation](https://github.com/eyecantell/cmdorc)
