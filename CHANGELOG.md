# Changelog

All notable changes to textual-cmdorc are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Logging Infrastructure**: Complete logging system for debugging and diagnostics
  - `setup_logging()` - Configure file-based logging with rotation (10MB, 5 backups)
  - `disable_logging()` - Remove all handlers and restore NullHandler
  - `get_log_file_path()` - Get path to log file for support/debugging
  - `get_logger()` - Get logger for textual-cmdorc modules
  - NullHandler by default (silent operation, library best practice)
  - CLI flags: `--log-file`, `--log-level`, `--log-all` for multi-package logging
  - `-v` / `--verbose` backward compatible alias for `--log-file`
  - Coordinates logging across textual-cmdorc, cmdorc, and textual-filelink
  - Default log location: `~/.cmdorc/logs/cmdorc-tui.log`
- Embeddable architecture with `CmdorcController` (non-Textual), passive `CmdorcView` widget, and thin `CmdorcApp` shell
- Real-time command status display with spinners, icons (✅/❌), play/stop buttons, and dynamic tooltips showing resolved commands
- Hierarchical tree view of commands, chains, and dependencies with duplicate indicators
- Configurable global keyboard shortcuts (1-9, a-z, F1-F12) via `[keyboard]` TOML section
- File watching integration with debounce, pattern matching, and ignored directories (`__pycache__`, `.git`, etc.)
- Toggleable log pane, modal help screen (`h`), details screen (`s`), and config reload (`r`)
- Command preview tooltips on play/stop buttons using resolved variables
- Comprehensive configuration validation with startup summaries
- Headless mode and event-driven callbacks for embedding in larger applications

### Changed
- Updated dependency on `cmdorc` to 0.9.0+ (adds logging support)
  - 0.8.1+ required for correct history ordering (most recent first)
  - 0.9.0+ includes `setup_logging()`, `disable_logging()`, `get_log_file_path()`
- Updated dependency on `textual-filelink` to 0.9.0+ (adds logging support)
- Removed global `logging.basicConfig()` from CLI (now silent by default with NullHandler)
- Improved tooltip content with semantic trigger summaries, full chains, keyboard hints, and duplicate markers

### Fixed
- Output file links now update correctly after multiple runs of the same command
- Ignored directories (`__pycache__`, `.git`, etc.) are properly filtered
- Various internal architectural issues ensuring thread-safety, async safety, and duplicate command tracking

### Breaking Changes
None - initial release.

### Migration Guide
For pre-release users:
- Update imports to `from textual_cmdorc import CmdorcApp, CmdorcController, CmdorcView`
- Add optional `[keyboard]` and `[[file_watcher]]` sections to your config
- See EMBEDDING.md for updated embedding patterns

### Contributors
- **eyecantell** - Lead developer and architect

### Credits
- Built on [Textual](https://textual.textualize.io/)
- Orchestration from [cmdorc](https://github.com/eyecantell/cmdorc)
- Widgets from [textual-filelink](https://github.com/eyecantell/textual-filelink)
- File watching via [watchdog](https://github.com/gorakhargosh/watchdog)