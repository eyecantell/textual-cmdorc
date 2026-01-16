# Changelog

All notable changes to textual-cmdorc are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Positional config file arguments (`cmdorc-tui dev.toml` or `cmdorc-tui dev.toml deploy.toml`)
  - Single file shows config name as static label
  - Multiple files create switchable configs with dropdown
  - Automatic naming from file stems with duplicate handling
  - Comprehensive error handling (missing files, wrong extensions, duplicates)

### Added
- Positional config file arguments (`cmdorc-tui dev.toml` or `cmdorc-tui dev.toml deploy.toml`)
  - Single file shows config name as static label
  - Multiple files create switchable configs with dropdown
  - Automatic naming from file stems with duplicate handling
  - Comprehensive error handling (missing files, wrong extensions, duplicates)

## [0.1.0] - 2026-01-12

### Added
- Embeddable architecture with `CmdorcWidget` (composable widget) and `CmdorcApp` (standalone wrapper)
- Real-time command status with spinners, icons (◯/⏳/✅/❌), play/stop buttons, and dynamic tooltips
- Flat list display of commands in TOML order with comprehensive tooltip system
- Configurable global keyboard shortcuts (1-9, a-z, F1-F12) via `[keyboard]` TOML section
- File watching with debounce, pattern matching, and ignored directories (`__pycache__`, `.git`, etc.)
- Modal help screen (`h`), command details screen (`s`), and live config reload (`r`)
- Command preview tooltips on play/stop buttons showing resolved commands
- Output file tooltips showing preview and status
- Comprehensive configuration validation with clear startup summaries
- Headless mode via `OrchestratorAdapter` for embedding in larger applications
- Comprehensive logging infrastructure (file-based, silent by default, opt-in via CLI flags)

### Changed
- Updated `cmdorc` dependency to 0.9.0+ (adds logging support; 0.8.1+ required for correct history ordering)
- Updated `textual-filelink` dependency to 0.9.0+ (adds logging support)
- Removed global `logging.basicConfig()` from CLI entrypoint (now silent by default)
- Enhanced tooltips with semantic trigger summaries, full chains, keyboard hints, and duplicate markers

### Fixed
- Output file links and tooltips now clear on command start and update correctly after multiple runs (no stale data)
- File watcher properly filters ignored directories
- Various internal issues for thread-safety, async safety, and accurate duplicate command tracking

### Breaking Changes
None - initial public release.

### Migration Guide
For pre-release or experimental users:
- Update imports: `from textual_cmdorc import CmdorcApp, CmdorcWidget`
- For headless/advanced embedding: `from cmdorc_frontend.orchestrator_adapter import OrchestratorAdapter`
- Add optional `[keyboard]` and `[[file_watcher]]` sections to config
- See README.md examples for embedding patterns

### Contributors
- **eyecantell** - Lead developer and architect

### Credits
- Built on [Textual](https://textual.textualize.io/) TUI framework
- Orchestration logic from [cmdorc](https://github.com/eyecantell/cmdorc)
- Interactive widgets from [textual-filelink](https://github.com/eyecantell/textual-filelink)
- File watching via [watchdog](https://github.com/gorakhargosh/watchdog)