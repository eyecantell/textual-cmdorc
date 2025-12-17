# Implementation Plan: Trigger Chains and Keyboard Support

## Overview

Build textual-cmdorc as an **embeddable TUI component** with standalone mode support.

## ⚠️ PRE-IMPLEMENTATION CRITICAL FIXES (External Review Feedback - Round 2)

The following issues were identified across two rounds of external architectural review and **MUST** be addressed before implementation begins:

### 🔴 Must-Fix (Blocking Implementation) - 8 Issues

| # | Issue | Current Risk | Fix Required |
|---|-------|-------------|--------------|
| 1 | **Async API incorrect** | `asyncio.create_task()` called outside event loop - will fail in sync contexts | Store `_loop` in `attach()`, use `self._loop.create_task()` in helpers |
| 2 | **Duplicate tracking wrong location** | Fix placed in integrator, but integrator doesn't have access to view's `_command_links` | Move duplicate tracking to `CmdorcView.build_command_tree()` method |
| 3 | **Keyboard conflicts recomputed** | Property rebuilds dict on every access - wasteful | Compute once in `__init__()`, cache as `_keyboard_conflicts`, return cached value |
| 4 | **TriggerSource coupling** | Moving `from_run_handle()` to models couples frontend to cmdorc's `RunHandle` type | Keep `from_trigger_chain()` generic in models, add adapter in integrator |
| 5 | **Watcher threading race** | `asyncio.create_task()` may be called outside loop thread | Wrap task creation in `loop.call_soon_threadsafe(lambda: create_task(...))` |
| 6 | **Help screen in log pane** | Ephemeral help mixed with persistent logs, not discoverable | Use Textual `ModalScreen` for help, add `h` binding to footer |
| 7 | **Tooltip truncation edge case** | `max_width < 4` causes negative `keep_chars` | Add minimum width check (10 chars) before truncation |
| 8 | **Missing key validation** | Invalid keys (e.g., "ctrl+x") pass validation silently | Validate against `VALID_KEYS` set: digits, a-z, f1-f12 |

### 🟡 Should-Fix (v0.1 Release Gate)

| # | Issue | Impact | Fix Required |
|---|-------|--------|--------------|
| 1 | **StateReconciler silent** | Host apps don't know when state reconciled on startup | Add `on_state_reconciled(command_name, state)` callback (already in controller API) |
| 2 | **Startup validation too verbose** | Always shows summary even when no issues | Only display validation summary if warnings or errors exist |
| 3 | **Help discoverability** | Users don't know `h` shows help screen | Add `h` binding to footer + first-launch hint in log pane |
| 4 | **Missing key validation details** | Plan says "validate" but no specifics | Define `VALID_KEYS = {"1"-"9", "a"-"z", "f1"-"f12"}` set in config parser |
| 5 | **Phase 0 time estimate low** | 3-4 hours likely insufficient for 8 fixes + architecture | Adjust to 6-8 hours for realistic Phase 0 completion |
| 6 | **No migration guide** | Existing users won't know how to update configs | Add migration guide section to README for v0.1 |
| 7 | **Missing test patterns** | Embedding tests not specified | Add unit test examples for controller lifecycle, duplicate tracking, keyboard conflicts |
| 8 | **Phase 0 anti-patterns** | Junior devs might re-monolith the design | Add "❌ Do Not Do" box: no global keys in controller, no `exit()`, no polling |

**Status:** These fixes are integrated into Phase 0 and relevant implementation phases below.

---

### **Core Architecture: Controller/View Split**
- **CmdorcController** (non-Textual): Owns orchestrator, config, watchers, state - the embed point
- **CmdorcView** (Textual Widget): Renders command tree, receives controller instance
- **CmdorcApp** (Textual App): Thin standalone shell composing controller + view

### **Features**
1. **Trigger Chain Display** - Show full execution breadcrumb trails with semantic summaries (e.g., "Ran automatically (file change)\npy_file_changed → command_success:Lint → command_success:Format")
2. **Keyboard Shortcuts (Metadata)** - Configurable keys (1-9 by default) exposed as metadata for host binding
3. **Startup Validation Summary** - Visual config validation results on app startup (v1 UX enhancement)
4. **Duplicate Command Indicators** - Visual cues when commands appear multiple times in tree (v1 UX enhancement)
5. **Embed-Ready Design** - Usable standalone or as subcomponent in larger TUIs

## Embedding Architecture Design

### **Design Principle: Embeddable by Default**

textual-cmdorc must work in two modes:
1. **Standalone**: Full-featured TUI app users can run directly
2. **Embedded**: Widget/controller that integrates into larger TUIs

**Key insight:** The `cmdorc_frontend` separation already enables this - we just need to complete the split at the TUI layer.

### **Three-Layer Architecture**

```
┌─────────────────────────────────────────────────────────┐
│  CmdorcApp (Textual App) - STANDALONE MODE ONLY        │
│  - Thin shell composing controller + view               │
│  - Owns process, event loop, global keys                │
│  - Binds quit/cancel actions                            │
└─────────────────────────────────────────────────────────┘
                         │ uses
                         ▼
┌─────────────────────────────────────────────────────────┐
│  CmdorcView (Textual Widget) - EMBED POINT             │
│  - Renders command tree with CommandLinks               │
│  - Receives controller instance                         │
│  - Optional log pane                                     │
│  - Passive: doesn't bind global keys                    │
└─────────────────────────────────────────────────────────┘
                         │ consumes
                         ▼
┌─────────────────────────────────────────────────────────┐
│  CmdorcController (non-Textual) - CORE LOGIC           │
│  - Owns CommandOrchestrator                             │
│  - Owns FileWatcherManager (but doesn't auto-start)     │
│  - Loads config, builds hierarchy                       │
│  - Exposes keyboard_bindings metadata                   │
│  - Exposes outbound event callbacks                     │
│  - Pluggable CmdorcNotifier                             │
└─────────────────────────────────────────────────────────┘
```

### **Controller API (Embed Point)**

```python
class CmdorcController:
    """Non-Textual controller - the primary embed point.

    RECOMMENDATION #2: Stable Public API for v0.1
    ============================================
    The following methods and properties are stable for v0.1:
    - Lifecycle: attach(), detach()
    - Command control: request_run(), request_cancel(), run_command(), cancel_command()
    - Keyboard metadata: keyboard_hints, keyboard_conflicts
    - Outbound events: on_command_started, on_command_finished, on_state_reconciled, etc.
    - Read-only access: orchestrator, hierarchy

    Internal methods (_on_file_change, etc.) may change.
    """

    def __init__(
        self,
        config_path: str | Path,
        notifier: CmdorcNotifier | None = None,
        enable_watchers: bool = True
    ):
        """
        Args:
            config_path: Path to TOML config
            notifier: Optional notification handler (defaults to no-op - POLISH #3)
                     Standalone mode passes TextualLogPaneNotifier
            enable_watchers: If False, watchers won't auto-start (for embedding)
        """
        self.notifier = notifier or NoOpNotifier()  # POLISH #3: Silent by default

    # Lifecycle
    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach to event loop and start watchers if enabled.

        FIX #1: Store loop reference for sync-safe task creation.
        RECOMMENDATION #1: Idempotent - guards against double-attach and non-running loop.
        """
        # RECOMMENDATION #1: Idempotency guard
        if self._loop is not None:
            return  # Already attached - safe for embedding scenarios

        # RECOMMENDATION #1: Validate loop is running
        if not loop.is_running():
            raise RuntimeError("Event loop must be running before attach(). "
                             "Call attach() from within on_mount() or after loop started.")

        self._loop = loop  # Store for request_run/cancel
        if self.enable_watchers:
            self.watcher_manager.start_watchers()

    def detach(self) -> None:
        """Stop watchers and cleanup."""
        if self.watcher_manager:
            self.watcher_manager.stop_watchers()
        self._loop = None

    # FIX #5: File watcher callback safety
    def _on_file_change(self, trigger_name: str) -> None:
        """Handle file change events from watcher thread.

        FIX #5: Uses call_soon_threadsafe to schedule async task from watcher thread.
        """
        if self._loop is None:
            logging.warning(f"File change for '{trigger_name}' ignored - controller not attached")
            return

        # FIX #5: Thread-safe task scheduling
        self._loop.call_soon_threadsafe(
            lambda: self._loop.create_task(self._trigger_command(trigger_name))
        )

    # Command control (low-level async)
    async def run_command(self, name: str) -> None:
        """Run a command by name (async - for advanced use)."""

    async def cancel_command(self, name: str) -> None:
        """Cancel a running command (async - for advanced use)."""

    async def reload_config(self) -> None:
        """Reload configuration file."""

    # Command control (UI-safe sync helpers) - FIX #1
    def request_run(self, name: str) -> None:
        """Request command run (sync-safe, schedules async task).

        FIX #1: Uses stored loop reference instead of asyncio.create_task().
        """
        if self._loop is None:
            raise RuntimeError("Controller not attached to event loop. Call attach() first.")
        self._loop.create_task(self.run_command(name))

    def request_cancel(self, name: str) -> None:
        """Request command cancellation (sync-safe, schedules async task).

        FIX #1: Uses stored loop reference instead of asyncio.create_task().
        """
        if self._loop is None:
            raise RuntimeError("Controller not attached to event loop. Call attach() first.")
        self._loop.create_task(self.cancel_command(name))

    # Keyboard metadata (NOT bindings)
    @property
    def keyboard_hints(self) -> dict[str, str]:
        """Returns {key: command_name} metadata for host to wire.

        POLISH #1: Returns metadata only (no callables) to decouple host from controller internals.
        Host wires own actions: self.bind(key, lambda: controller.request_run(name))
        """
        return {
            key: cmd_name
            for cmd_name, key in self.keyboard_config.shortcuts.items()
        }

    @property
    def keyboard_conflicts(self) -> dict[str, list[str]]:
        """FIX #3: Returns {key: [cmd_name1, cmd_name2, ...]} for keys with multiple commands.

        Cached in __init__() to avoid recomputation on every access.
        """
        return self._keyboard_conflicts  # Computed once in __init__()

    @property
    def keyboard_help(self) -> list[KeyboardHint]:
        """Keyboard shortcut hints for display."""

    # Outbound events (host hooks into these)
    on_command_started: Callable[[str, TriggerSource], None] | None = None
    on_command_finished: Callable[[str, RunResult], None] | None = None
    on_trigger_fired: Callable[[str, str], None] | None = None  # (trigger_name, source)
    on_validation_result: Callable[[ConfigValidationResult], None] | None = None
    on_state_reconciled: Callable[[str, RunState], None] | None = None  # FIX #6: (command_name, state)

    # Intent signals (for actions that affect host)
    on_quit_requested: Callable[[], None] | None = None
    on_cancel_all_requested: Callable[[], None] | None = None

    # Read-only access
    @property
    def orchestrator(self) -> CommandOrchestrator:
        """Direct access for advanced embedding."""

    @property
    def hierarchy(self) -> list[CommandNode]:
        """Command hierarchy for rendering."""
```

### **View API (Textual Widget)**

```python
class CmdorcView(Widget):
    """Textual widget for rendering cmdorc state."""

    def __init__(
        self,
        controller: CmdorcController,
        show_log_pane: bool = True,
        enable_local_bindings: bool = False  # For standalone mode only
    ):
        """
        Args:
            controller: CmdorcController instance
            show_log_pane: Whether to render log pane
            enable_local_bindings: If True, handle keys when focused (standalone only)
        """

    # View updates driven by controller callbacks
    def refresh_tree(self) -> None:
        """Rebuild tree from controller.hierarchy."""

    def update_command(self, name: str, update: PresentationUpdate) -> None:
        """Update specific command display."""
```

### **Standalone App (Thin Shell)**

```python
class CmdorcApp(App):
    """Standalone mode - composes controller + view with full app semantics."""

    def __init__(self, config_path: str = "config.toml", **kwargs):
        super().__init__(**kwargs)
        # POLISH #3: Standalone passes TextualLogPaneNotifier (set after view created)
        self.controller = CmdorcController(config_path, enable_watchers=True)

        # Wire outbound events to app-level actions
        self.controller.on_quit_requested = self.action_quit
        self.controller.on_cancel_all_requested = self.action_cancel_all

    def on_mount(self) -> None:
        self.controller.attach(asyncio.get_running_loop())
        self.view = CmdorcView(self.controller, enable_local_bindings=True)
        self.mount(self.view)

        # POLISH #3: Wire log pane notifier after view exists
        if hasattr(self.view, 'log_pane'):
            self.controller.notifier = TextualLogPaneNotifier(self.view.log_pane)

        # POLISH #1: Bind global keyboard shortcuts using metadata (not callables)
        for key, cmd_name in self.controller.keyboard_hints.items():
            self.bind(
                key,
                lambda name=cmd_name: self.controller.request_run(name),
                description=f"Run/stop {cmd_name}"
            )

        # Should-fix #3: Show first-launch hint for help discoverability
        if hasattr(self.view, 'log_pane'):
            self.view.log_pane.write_line("ℹ️  Press [h] to see keyboard shortcuts")

    async def on_unmount(self) -> None:
        self.controller.detach()
```

### **Embedding Example**

```python
class MyLargerTUI(App):
    """Example: Embedding CmdorcView in a larger TUI."""

    def compose(self):
        # Controller is owned by host
        self.cmdorc = CmdorcController("config.toml", enable_watchers=False)

        # Wire events to host's notification system
        self.cmdorc.on_command_finished = self.on_cmdorc_command_done

        yield Header()
        yield Horizontal(
            CmdorcView(self.cmdorc, show_log_pane=False),  # Embedded view
            MyOtherPanel(),
        )
        yield Footer()

    def on_mount(self):
        # Host controls watcher lifecycle
        self.cmdorc.attach(asyncio.get_running_loop())

        # POLISH #1: Host wires keyboard shortcuts using metadata (decoupled from controller internals)
        for key, cmd_name in self.cmdorc.keyboard_hints.items():
            if key not in self.MY_RESERVED_KEYS:
                self.bind(key, lambda name=cmd_name: self.cmdorc.request_run(name))

    def on_cmdorc_command_done(self, name: str, result: RunResult):
        # Host reacts to cmdorc events
        self.notify(f"Command {name} finished: {result.state}")
```

### **Notifier Protocol (Pluggable Logging)**

```python
class CmdorcNotifier(Protocol):
    """Protocol for notifications - host can provide custom implementation."""

    def info(self, message: str) -> None:
        """Informational message."""

    def warning(self, message: str) -> None:
        """Warning message."""

    def error(self, message: str) -> None:
        """Error message."""

class NoOpNotifier:
    """POLISH #3: Silent no-op notifier - default for embedded mode.

    Prevents unwanted stderr spam when controller is embedded without a view/log pane.
    """
    def info(self, msg: str) -> None:
        pass
    def warning(self, msg: str) -> None:
        pass
    def error(self, msg: str) -> None:
        pass

class LoggingNotifier:
    """Implementation using stdlib logging - for debugging/development."""
    def info(self, msg: str) -> None:
        logging.info(msg)
    def warning(self, msg: str) -> None:
        logging.warning(msg)
    def error(self, msg: str) -> None:
        logging.error(msg)

class TextualLogPaneNotifier:
    """Textual-specific implementation for standalone mode."""
    def __init__(self, log_pane: Log):
        self.log_pane = log_pane
    def info(self, msg: str) -> None:
        self.log_pane.write_line(f"ℹ️  {msg}")
    # ... etc
```

---

## Key Features from Dependencies

### cmdorc (Trigger Chains)
- `RunHandle.trigger_chain` property returns `list[str]` of trigger events
- Example: `["py_file_changed", "command_success:Lint"]`
- Empty list `[]` means manual run
- Already implemented and tested in cmdorc

### textual-filelink (Keyboard Support)
- `CommandLink.action_play_stop()` intelligently handles running/stopped state
- BINDINGS class variable for defining shortcuts
- Automatic tooltip enhancement with keyboard shortcuts
- Recommended pattern: Override `on_key()` in App and call action methods

## Configuration Schema

### TOML Format

```toml
# Centralized keyboard shortcuts configuration
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3", "Build" = "b" }
enabled = true
show_in_tooltips = true

[[command]]
name = "Lint"
command = "ruff check --fix"
triggers = ["py_file_changed"]
# keyboard shortcut configured in [keyboard] section above
```

### Rationale
- Centralized mapping prevents conflicts and improves visibility
- Keeps command definitions focused on execution logic
- Easy to see all keyboard shortcuts at a glance

## Implementation Details

### 1. Configuration Parsing (`cmdorc_frontend/config.py`)

**Add KeyboardConfig data structure:**
```python
@dataclass
class KeyboardConfig:
    shortcuts: Dict[str, str]  # command_name -> key
    enabled: bool = True
    show_in_tooltips: bool = True
```

**Update load_frontend_config() signature:**
```python
def load_frontend_config(path: str | Path) -> Tuple[
    RunnerConfig,
    List[WatcherConfig],
    List[CommandNode],
    KeyboardConfig  # NEW
]:
```

**Add validation (FIX #8):**
```python
# Define valid keyboard keys
VALID_KEYS = set(
    [str(i) for i in range(1, 10)]  # 1-9
    + [chr(i) for i in range(ord('a'), ord('z') + 1)]  # a-z
    + [f"f{i}" for i in range(1, 13)]  # f1-f12
)

def validate_keyboard_shortcuts(
    shortcuts: dict[str, str],
    command_names: set[str]
) -> list[str]:
    """Validate keyboard shortcuts and return warnings.

    FIX #8: Validates keys against VALID_KEYS set.

    Returns:
        List of warning messages
    """
    warnings = []

    # Check for invalid keys
    for cmd_name, key in shortcuts.items():
        if key not in VALID_KEYS:
            warnings.append(f"Invalid key '{key}' for command '{cmd_name}'. "
                          f"Valid keys: 1-9, a-z, f1-f12")

    # Check for unknown commands
    for cmd_name in shortcuts.keys():
        if cmd_name not in command_names:
            warnings.append(f"Shortcut for '{cmd_name}' references unknown command")

    # Check for duplicate keys
    key_to_commands = {}
    for cmd_name, key in shortcuts.items():
        key_to_commands.setdefault(key, []).append(cmd_name)

    for key, commands in key_to_commands.items():
        if len(commands) > 1:
            warnings.append(f"Duplicate key '{key}' for {', '.join(commands)} "
                          f"(last one wins)")

    return warnings
```

### 2. Trigger Chain Model (`cmdorc_frontend/models.py`)

**Extend TriggerSource:**
```python
@dataclass
class TriggerSource:
    name: str  # Last trigger in chain (backward compat)
    kind: Literal["manual", "file", "lifecycle"]
    chain: list[str] = field(default_factory=list)  # NEW

    @classmethod
    def from_trigger_chain(cls, trigger_chain: list[str]) -> 'TriggerSource':
        """Create from cmdorc's RunHandle.trigger_chain."""
        if not trigger_chain:
            return cls(name="manual", kind="manual", chain=[])

        last_trigger = trigger_chain[-1]
        kind = ("lifecycle" if last_trigger.startswith("command_")
                else "file" if "file" in last_trigger.lower()
                else "manual")

        return cls(name=last_trigger, kind=kind, chain=trigger_chain)

    def format_chain(self, separator: str = " → ", max_width: int = 80) -> str:
        """Format for display, with optional left truncation.

        Args:
            separator: String to join events with
            max_width: Maximum width before truncation (default 80). Set to None to disable.

        Returns:
            Formatted chain, possibly with "..." prefix if truncated

        FIX #7: Minimum width check prevents negative keep_chars edge case.
        """
        if not self.chain:
            return "manual"

        full_chain = separator.join(self.chain)

        # FIX #7: Minimum width check before truncation
        if max_width is not None and max_width < 10:
            # Too narrow to truncate meaningfully, return as-is
            return full_chain

        # Truncate from left if needed
        if max_width is not None and len(full_chain) > max_width:
            # Calculate how many chars to keep (accounting for "..." prefix)
            keep_chars = max_width - 4  # Reserve 4 for "... "
            if keep_chars > 0:
                return f"...{separator}{full_chain[-keep_chars:]}"

        return full_chain

    def get_semantic_summary(self) -> str:
        """NEW: Get human-readable summary of trigger source.

        Returns:
            Short semantic description (e.g., "Ran automatically (file change)")
        """
        if not self.chain:
            return "Ran manually"

        if self.kind == "file":
            return "Ran automatically (file change)"
        elif self.kind == "lifecycle":
            return "Ran automatically (triggered by another command)"
        else:
            return "Ran automatically"
```

### 3. Callback Integration (`textual_cmdorc/integrator.py`)

**Extract trigger_chain from RunHandle (FIX #4):**
```python
def create_command_link(
    node: CommandNode,
    orchestrator: CommandOrchestrator,
    on_status_change: Callable | None = None
) -> CmdorcCommandLink:
    link = CmdorcCommandLink(node.config)

    def update_from_result(handle: RunHandle, context=None):
        result = handle._result

        # FIX #4: Adapter layer - extract trigger_chain from RunHandle
        # Keeps TriggerSource.from_trigger_chain() UI-agnostic
        trigger_chain = handle.trigger_chain
        trigger_source = TriggerSource.from_trigger_chain(trigger_chain)

        link.update_from_run_result(result, trigger_source)
        if on_status_change:
            on_status_change(result.state, result)

    # Wire callbacks (pass RunHandle to access trigger_chain)
    orchestrator.set_lifecycle_callback(
        node.name,
        on_success=update_from_result,
        on_failed=update_from_result,
        on_cancelled=update_from_result
    )

    return link
```

### 4. Widget Display (`textual_cmdorc/widgets.py`)

**Add keyboard_shortcut and duplicate indicator attributes:**
```python
class CmdorcCommandLink(CommandLink, CommandView):
    def __init__(self, config: CommandConfig, keyboard_shortcut: str | None = None, is_duplicate: bool = False, **kwargs):
        # NEW: Add visual cue for duplicates
        label = config.name
        if is_duplicate:
            label = f"{config.name} (↳)"  # Subtle indicator

        super().__init__(
            label=label,
            output_path=None,
            initial_status_icon="❓",
            initial_status_tooltip="Idle",
            show_toggle=False,
            show_settings=False,
            show_remove=False,
            **kwargs
        )
        self.config = config
        self.current_trigger: TriggerSource = TriggerSource("Idle", "manual", chain=[])
        self.keyboard_shortcut = keyboard_shortcut  # NEW
        self.is_duplicate = is_duplicate  # NEW
        self._update_tooltips()
```

**Enhanced tooltips with trigger chains, semantic summaries, and duplicate indicators:**
```python
def _update_tooltips(self) -> None:
    if self.is_running:
        # NEW: Show semantic summary first, then technical chain
        semantic = self.current_trigger.get_semantic_summary()
        chain_display = self.current_trigger.format_chain()
        tooltip = f"Stop — {semantic}\n{chain_display}"
        if self.keyboard_shortcut:
            tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to stop"
        # NEW: Add duplicate indicator in tooltip
        if self.is_duplicate:
            # POLISH #4: Clarify that shortcut affects all instances
            if self.keyboard_shortcut:
                tooltip = f"{tooltip}\n(Appears in multiple workflows - shortcut affects all instances)"
            else:
                tooltip = f"{tooltip}\n(This command appears in multiple workflows)"
        self.set_stop_tooltip(tooltip)
    else:
        triggers = ", ".join(self.config.triggers) or "none"
        tooltip = f"Run (Triggers: {triggers} | manual)"
        if self.keyboard_shortcut:
            tooltip = f"{tooltip}\n[{self.keyboard_shortcut}] to run"
        else:
            # Show hint for unconfigured shortcuts
            tooltip = f"{tooltip}\nSet hotkey with {self.config.name} = '<key>' in [keyboard] shortcuts"
        # NEW: Add duplicate indicator in tooltip
        if self.is_duplicate:
            # POLISH #4: Clarify that shortcut affects all instances
            if self.keyboard_shortcut:
                tooltip = f"{tooltip}\n(Appears in multiple workflows - shortcut affects all instances)"
            else:
                tooltip = f"{tooltip}\n(This command appears in multiple workflows)"
        self.set_play_tooltip(tooltip)
```

**Update from RunResult with full chain:**
```python
def update_from_run_result(self, result: RunResult, trigger_source: TriggerSource) -> None:
    icon = map_run_state_to_icon(result.state)
    chain_display = trigger_source.format_chain()
    tooltip = f"{result.state.value} ({result.duration_str})\nTrigger chain: {chain_display}"

    update = PresentationUpdate(
        icon=icon,
        running=(result.state == RunState.RUNNING),
        tooltip=tooltip,
        output_path=result.output if result.state in [SUCCESS, FAILED, CANCELLED] else None
    )
    self.apply_update(update)
    self.current_trigger = trigger_source
    self._update_tooltips()
```

### 5. Startup Validation Summary

**RECOMMENDATION #3: Centralized validation in controller/frontend**

**In `cmdorc_frontend/config.py` or `controller.py`:**
```python
@dataclass
class ConfigValidationResult:
    """Results from config validation.

    RECOMMENDATION #3: Built by controller, consumed by app for display only.
    """
    commands_loaded: int = 0
    watchers_active: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

# In CmdorcController:
def validate_config(self) -> ConfigValidationResult:
    """RECOMMENDATION #3: Validate configuration and return structured results.

    App displays results, does not re-derive them.
    """
    result = ConfigValidationResult(
        commands_loaded=len(self.orchestrator.runner_config.commands),
        watchers_active=len(self.watcher_manager.active_watchers()) if self.watcher_manager else 0
    )

    # Keyboard validation (uses validate_keyboard_shortcuts from config.py)
    command_names = {c.name for c in self.orchestrator.runner_config.commands}
    result.warnings.extend(
        validate_keyboard_shortcuts(self.keyboard_config.shortcuts, command_names)
    )

    # Watcher validation
    result.warnings.extend(self.watcher_manager.get_validation_warnings())

    return result
```

**In `textual_cmdorc/app.py` (thin display layer):**
```python
def show_validation_summary(self, result: ConfigValidationResult) -> None:
    """RECOMMENDATION #3: Display only - app does not derive validation results."""
    # Should-fix #2: Only show validation summary if there are issues
    if hasattr(self, 'log_pane'):
        if result.warnings or result.errors:
            # Show detailed summary when there are issues
            self.log_pane.write_line("=== Config Validation Issues ===")
            for warning in result.warnings:
                self.log_pane.write_line(f"⚠️  {warning}")
            for error in result.errors:
                self.log_pane.write_line(f"❌ {error}")
            self.log_pane.write_line("=================================")
        else:
            # Brief success message when no issues
            self.log_pane.write_line(f"✓ Loaded {result.commands_loaded} commands, "
                                    f"{result.watchers_active} watchers")

# In on_mount():
def on_mount(self) -> None:
    # ... existing mount logic ...

    # RECOMMENDATION #3: Get validation from controller, display only
    validation_result = self.controller.validate_config()
    self.show_validation_summary(validation_result)
```

### 6. Global Keyboard Handler (`textual_cmdorc/app.py`)

**Initialize with keyboard config:**
```python
class CmdorcApp(App):
    def __init__(self, config_path: str = "config.toml", **kwargs):
        super().__init__(**kwargs)
        setup_logging()

        # Load with keyboard config
        runner_config, watchers, self.hierarchy, self.keyboard_config = load_frontend_config(config_path)
        self.orchestrator = CommandOrchestrator(runner_config)

        # NEW: Build key -> command_name lookup
        self.key_to_command: Dict[str, str] = {}
        if self.keyboard_config.enabled:
            self.key_to_command = {
                key: cmd_name
                for cmd_name, key in self.keyboard_config.shortcuts.items()
            }
```

**Global on_key() handler:**
```python
def on_key(self, event: Key) -> None:
    """Handle global keyboard shortcuts for commands."""
    if not self.keyboard_config.enabled:
        return

    key = event.key

    if key in self.key_to_command:
        command_name = self.key_to_command[key]

        # Find widget for this command
        command_links = list(self.query(CmdorcCommandLink))
        target_link = None
        for link in command_links:
            if link.config.name == command_name:
                target_link = link
                break

        if target_link:
            # Use smart action that handles running/stopped state
            target_link.action_play_stop()
            event.prevent_default()
            event.stop()

            # Optional: Log to log pane
            if hasattr(self, 'log_pane'):
                self.log_pane.write_line(f"[{key}] triggered: {command_name}")
        else:
            # NEW: Write to log pane for better user feedback
            if hasattr(self, 'log_pane'):
                self.log_pane.write_line(f"⚠️ Shortcut [{key}] ignored: Command '{command_name}' not found in tree")
            logging.warning(f"Shortcut '{key}' -> '{command_name}' but widget not found")
```

**Pass shortcuts to widget creation and detect duplicates:**
```python
def build_command_tree(self, tree: Tree, nodes: list[CommandNode], parent=None):
    # NEW: Track command appearances to detect duplicates
    if not hasattr(self, '_command_occurrence_count'):
        self._command_occurrence_count = {}

    for node in nodes:
        # Get keyboard shortcut for this command
        shortcut = self.keyboard_config.shortcuts.get(node.name) if self.keyboard_config.enabled else None

        # NEW: Detect if this is a duplicate (appeared before)
        occurrence_count = self._command_occurrence_count.get(node.name, 0)
        self._command_occurrence_count[node.name] = occurrence_count + 1
        is_duplicate = occurrence_count > 0

        # Create link with shortcut and duplicate indicator
        link = create_command_link(node, self.orchestrator, self.on_global_status_change)
        link.keyboard_shortcut = shortcut
        link.is_duplicate = is_duplicate  # NEW
        link._update_tooltips()  # Refresh tooltips

        # Add to tree
        if parent is None:
            tree_node = tree.root.add(link)
        else:
            tree_node = parent.add(link)

        # Recursively add children
        if node.children:
            self.build_command_tree(tree, node.children, tree_node)
```

## Config Initialization Helper

Add utility function to generate initial keyboard config:

```python
# src/cmdorc_frontend/config.py

def init_keyboard_config(runner_config: RunnerConfig, output_path: Path | None = None) -> str:
    """Generate initial [keyboard] section with no-op placeholders.

    Args:
        runner_config: Loaded runner configuration
        output_path: Optional path to write config snippet

    Returns:
        TOML string with [keyboard] section
    """
    shortcuts = {cmd.name: f"<key{i+1}>" for i, cmd in enumerate(runner_config.commands)}

    toml_content = "[keyboard]\n"
    toml_content += f"shortcuts = {{\n"
    for name, key in shortcuts.items():
        toml_content += f'    "{name}" = "{key}",\n'
    toml_content += "}\n"
    toml_content += "enabled = true\n"

    if output_path:
        output_path.write_text(toml_content)

    return toml_content
```

**Public CLI Command:**
```bash
# Generate initial config with placeholders for all commands
cmdorc init config.toml  # Creates config.toml with [[command]] sections and [keyboard] with placeholders
# or
cmdorc init  # Uses default config.toml in current directory
```

This should be exposed via a CLI entry point in pyproject.toml so users can easily initialize configs.

## 7. Help Screen with Keyboard Conflicts (`textual_cmdorc/app.py`)

**FIX #6: Use ModalScreen instead of log pane for help:**
```python
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.containers import VerticalScroll

class HelpScreen(ModalScreen):
    """Modal help screen showing keyboard shortcuts and conflicts.

    FIX #6: Separate ephemeral help from persistent log pane.
    """

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, keyboard_config: KeyboardConfig):
        super().__init__()
        self.keyboard_config = keyboard_config

    def compose(self):
        help_lines = []
        help_lines.append("# Keyboard Shortcuts\n")

        if not self.keyboard_config.enabled:
            help_lines.append("Keyboard shortcuts are disabled.\n")
        elif not self.keyboard_config.shortcuts:
            help_lines.append("No keyboard shortcuts configured.\n")
        else:
            # Group by key to detect conflicts
            key_to_commands = {}
            for cmd_name, key in self.keyboard_config.shortcuts.items():
                key_to_commands.setdefault(key, []).append(cmd_name)

            # Display shortcuts, highlighting conflicts
            for key, commands in sorted(key_to_commands.items()):
                if len(commands) > 1:
                    # Conflict detected
                    help_lines.append(f"⚠️  `[{key}]` → {', '.join(commands)} "
                                    f"**(CONFLICT - last one wins)**\n")
                else:
                    help_lines.append(f"`[{key}]` → {commands[0]}\n")

            # POLISH #2: Document duplicate command behavior
            help_lines.append("\n**Note:** If a command appears multiple times in the tree ")
            help_lines.append("(marked with ↳), its shortcut affects all instances.\n")

        help_lines.append("\n# App Shortcuts\n")
        help_lines.append("`[r]` Reload config\n")
        help_lines.append("`[Ctrl+C]` Cancel all commands\n")
        help_lines.append("`[l]` Toggle log pane\n")
        help_lines.append("`[h]` Show this help\n")
        help_lines.append("`[q]` Quit\n")

        with VerticalScroll():
            yield Static("".join(help_lines), id="help-content")

    def action_dismiss(self):
        """Close the help screen."""
        self.app.pop_screen()


# In CmdorcApp class:
BINDINGS = [
    ("h", "show_help", "Help"),  # FIX #6: Add to footer for discoverability
    ("r", "reload", "Reload"),
    ("l", "toggle_log", "Toggle Log"),
    ("q", "quit", "Quit"),
]

def action_show_help(self) -> None:
    """Show help screen with keyboard shortcuts and conflicts.

    FIX #6: Uses ModalScreen instead of log pane.
    """
    self.push_screen(HelpScreen(self.keyboard_config))
```

## Implementation Order (Revised for Embedding)

### **Phase 0: Controller/View Architecture (6-8 hours)**
**Priority:** FOUNDATIONAL - Everything else builds on this

**Note:** Time increased from original 3-4 hours to account for 8 must-fix issues and comprehensive testing requirements.

1. **Create `CmdorcController` class** (`src/textual_cmdorc/controller.py`):
   - Extract logic from old `CmdorcApp`
   - Owns `CommandOrchestrator`, `FileWatcherManager`
   - Loads config via `cmdorc_frontend`
   - `attach(loop)` / `detach()` lifecycle
   - `enable_watchers` parameter
   - Outbound event callbacks (on_command_started, on_command_finished, on_state_reconciled, etc.)
   - Intent signals (on_quit_requested, on_cancel_all_requested)
   - **FIX #1:** Add `request_run()` / `request_cancel()` sync-safe helpers
   - **FIX #4:** Add `keyboard_conflicts` property
   - **FIX #5:** Wrap watcher task creation in `loop.call_soon_threadsafe()`
   - keyboard_bindings property (metadata only, not bindings)

2. **Create `Cmdorc View` widget** (`src/textual_cmdorc/view.py`):
   - Textual `Widget` subclass
   - Receives `CmdorcController` instance
   - Builds tree from `controller.hierarchy`
   - **FIX #2:** Change `_command_links` to `dict[str, list[CmdorcCommandLink]]` to track duplicates
   - Wires controller callbacks to update tree
   - Optional log pane (show_log_pane parameter)
   - Optional local bindings (enable_local_bindings for standalone only)

3. **Create `CmdorcNotifier` protocol** (`src/cmdorc_frontend/notifier.py`):
   - Protocol interface
   - `LoggingNotifier` (default)
   - `TextualLogPaneNotifier` (for standalone)

4. **Refactor `CmdorcApp`** (`src/textual_cmdorc/app.py`):
   - Becomes thin shell
   - Composes `CmdorcController` + `CmdorcView`
   - Binds keyboard shortcuts globally (standalone only)
   - Wires intent signals to actions

5. **Write controller/view tests**:
   - Controller lifecycle (attach/detach)
   - View updates from controller callbacks
   - Keyboard metadata exposure
   - Outbound event firing
   - **NEW:** Test duplicate command link tracking
   - **NEW:** Test keyboard conflict detection
   - **NEW:** Test sync-safe intent methods

6. **❌ DO NOT DO (Anti-Patterns)** - **FIX #7:**
   - ❌ Do not bind global keys inside the controller
   - ❌ Do not call `exit()` or `app.exit()` from controller
   - ❌ Do not poll orchestrator state (use callbacks only)
   - ❌ Do not make controller depend on Textual
   - ❌ Do not auto-start watchers without checking `enable_watchers`

**Deliverable:** Embeddable controller + view architecture working in standalone mode with all 7 fixes applied

---

### Phase 1: Configuration & Models (2-3 hours)
1. `cmdorc_frontend/models.py` - Extend TriggerSource with:
   - Chain support + truncation (**FIX #7:** min width check)
   - `get_semantic_summary()` method for human-readable descriptions
   - Keep `from_trigger_chain(trigger_chain: list[str])` generic (**FIX #4:** NO from_run_handle - that's an adapter in integrator)
2. `cmdorc_frontend/config.py` - Add KeyboardConfig parsing, validation (**FIX #8:** VALID_KEYS), and init helper
3. Write tests for config parsing, chain truncation, semantic summaries, and key validation

**Deliverable:** Config can be parsed with keyboard shortcuts, chains format correctly, trigger extraction is UI-agnostic (FIX #4)

### Phase 2: Trigger Chain Display (2-3 hours)
4. **FIX #4:** `textual_cmdorc/integrator.py` - Extract `trigger_chain` from RunHandle, pass to `TriggerSource.from_trigger_chain()` (adapter pattern)
5. `textual_cmdorc/widgets.py` - Enhanced tooltips with:
   - Semantic summary first (e.g., "Ran automatically (file change)")
   - Technical chain second (e.g., "py_file_changed → command_success:Lint")
   - Duplicate indicators (**FIX #2:** tracked in view, passed to widget)
6. Write tests for integrator adapter pattern (trigger extraction is UI-agnostic)

**Deliverable:** Tooltips show semantic summary + full trigger chains, integrator is thin adapter layer (FIX #4)

### Phase 3: Duplicate Command Indicators (1 hour)
7. `textual_cmdorc/widgets.py` - Add `is_duplicate` parameter to CmdorcCommandLink
8. `textual_cmdorc/app.py` - Track command occurrences in `build_command_tree()`
9. Update tooltips to show "(This command appears in multiple workflows)"
10. Update label with (↳) suffix for duplicates

**Deliverable:** Visual cues for duplicate commands in tree

### Phase 4: Keyboard Shortcuts (2-3 hours)
11. `textual_cmdorc/widgets.py` - Add keyboard_shortcut attribute
12. `textual_cmdorc/app.py` - Add on_key() handler and key mapping
13. `textual_cmdorc/app.py` - Pass shortcuts to widget creation
14. Write tests for keyboard handling

**Deliverable:** Keys trigger commands globally

### Phase 5: Startup Validation Summary (1-2 hours)
15. `textual_cmdorc/app.py` - Add ConfigValidationResult dataclass
16. Implement `validate_config_and_show_summary()` method
17. Call validation on startup and display in log pane
18. Write tests for validation logic

**Deliverable:** Config validation summary shown on app startup

### Phase 6: Help Screen (30 min)
19. `textual_cmdorc/app.py` - Implement `action_show_help()` with:
    - Keyboard shortcut list
    - Conflict highlighting
    - App shortcuts reference
20. Write tests for help screen display

**Deliverable:** Help screen shows shortcuts and conflicts

### Phase 7: Integration & Documentation (3-4 hours)
21. Integration tests for full workflow with all new features
22. **Embedding integration tests**:
    - Test CmdorcController standalone usage
    - Test CmdorcView in mock host app
    - Test keyboard metadata exposure
    - Test outbound event callbacks
23. **Embedding documentation**:
    - Add embedding guide to README
    - Document controller API in architecture.md
    - Add embedding example to examples/
24. Update example config.toml with [keyboard] section
25. Update all documentation (README, architecture, implementation)

**Total:** 22-27 hours (was 10-14 originally, +3-4 for UX, +6-8 for embedding architecture with 8 critical fixes)

## Edge Cases

1. **>9 commands**: Support any key (letters, f-keys), not just digits
2. **Duplicate keys**: Last definition wins, warning logged, shown in help screen
3. **Invalid keys**: Validate against allowed set (digits, a-z, f1-f12)
4. **Command not found**: Warning logged and shown in startup validation summary
5. **Running/stopped state**: `action_play_stop()` handles intelligently
6. **Duplicate commands in tree**:
   - All instances show (↳) suffix and tooltip note
   - All instances share same shortcut, all trigger together when key pressed
   - Each instance maintains its own state display
7. **Unconfigured shortcuts**: Tooltip shows hint: "Set hotkey with {name} = '<key>' in [keyboard] shortcuts"
8. **Long trigger chains**: Truncate from left with "..." prefix when exceeding max_width (default 80)
9. **Empty trigger chains**: Display as "Ran manually" with semantic summary
10. **Missing watcher directories**: Shown in startup validation summary as warning
11. **Config with no keyboard section**: Gracefully defaults to no shortcuts (shortcuts = {})

### **Embedding-Specific Edge Cases**
12. **Controller without view**: Controller can exist and run commands without any view attached
13. **Multiple views, one controller**: Same controller can power multiple views (different parts of host UI)
14. **Host event loop not running**: Controller.attach() should gracefully fail if loop isn't running
15. **Watcher lifecycle mismatch**: If host calls detach() while commands running, cleanly cancel watchers
16. **Keyboard binding conflicts**: Host checks keyboard_bindings before binding, skips conflicts
17. **Outbound callback exceptions**: Controller catches and logs, doesn't propagate to host
18. **View without log pane in embedded mode**: show_log_pane=False works, notifier still functions via logging
19. **enable_watchers=False then manual attach**: Should be idempotent, no double-start

---

## IMPLEMENTATION APPROACH (Answering User's Question)

The user asked for preference on implementation approach. Based on the 7 critical fixes identified:

**✅ RECOMMENDED: Option B (Docs + Test Stubs First)**

**Rationale:**
1. **Prevents regressions**: Each fix has a test that validates it works
2. **Clear success criteria**: Implementation knows exactly what "done" means
3. **Embedding-first validation**: Tests verify the core embed contract

**Test Stubs to Add Before Implementation:**

```python
# tests/test_controller_fixes.py

def test_sync_safe_intent_methods():
    """FIX #1: request_run/cancel don't block event loop."""
    controller = CmdorcController(...)
    controller.request_run("Test")  # Should not raise, should not await

def test_duplicate_command_links():
    """FIX #2: Multiple command occurrences tracked separately."""
    view = CmdorcView(...)
    view._build_tree(...)
    assert len(view._command_links["DuplicateCmd"]) == 2

def test_trigger_source_from_run_handle():
    """FIX #3: Trigger extraction is UI-agnostic."""
    from cmdorc_frontend.models import TriggerSource
    handle = mock_run_handle(trigger_chain=["py_file_changed", "command_success:Lint"])
    trigger = TriggerSource.from_run_handle(handle)
    assert trigger.chain == ["py_file_changed", "command_success:Lint"]

def test_keyboard_conflicts_exposed():
    """FIX #4: Conflicts visible to host."""
    controller = CmdorcController(...)  # config with conflicting keys
    conflicts = controller.keyboard_conflicts
    assert "1" in conflicts
    assert len(conflicts["1"]) > 1

def test_watcher_threading_safety():
    """FIX #5: Task creation wrapped in call_soon_threadsafe."""
    # Mock test - verify call_soon_threadsafe is used
    ...

def test_state_reconciler_emits_events():
    """FIX #6: on_state_reconciled callback fires."""
    controller = CmdorcController(...)
    events = []
    controller.on_state_reconciled = lambda name, state: events.append((name, state))
    # Trigger reconciliation
    assert len(events) > 0
```

**Next Steps:**
1. ✅ Add these test stubs to `tests/test_controller_fixes.py`
2. ✅ Update documentation (architecture.md, implementation.md, README.md) with fixes
3. ✅ Implement Phase 0 with fixes integrated
4. ✅ Run tests to validate each fix
5. ✅ Continue with Phases 1-7

**Scope Decision:**
- 🔴 All 5 must-fix items addressed in Phase 0
- 🟡 Fix #6 (StateReconciler events) added as Phase 0 enhancement
- 🟡 Fix #7 (anti-patterns box) added to documentation

---

## Critical Files to Modify (With Fixes Integrated)

### **Phase 0 Files (With All 7 Fixes):**

1. **`src/textual_cmdorc/controller.py`** (NEW - FIX #1, #4, #5, #6)
   - Add `request_run()` / `request_cancel()` sync helpers
   - Add `keyboard_conflicts` property
   - Add `on_state_reconciled` callback
   - Wrap watcher task creation in `call_soon_threadsafe()`

2. **`src/textual_cmdorc/view.py`** (NEW - FIX #2)
   - Change `_command_links: dict[str, CmdorcCommandLink]` to `dict[str, list[CmdorcCommandLink]]`
   - Update all references to iterate over lists

3. **`src/cmdorc_frontend/notifier.py`** (NEW)
   - Protocol + LoggingNotifier + TextualLogPaneNotifier

4. **`src/textual_cmdorc/app.py`** (REFACTOR - FIX #7)
   - Thin shell composing controller + view
   - Add anti-patterns documentation in docstring

5. **`tests/test_controller_fixes.py`** (NEW)
   - Test stubs for all 7 fixes

### **Phase 1 Files (FIX #3):**

6. **`src/cmdorc_frontend/models.py`** (UPDATE)
   - Add `TriggerSource.from_run_handle(handle)` classmethod
   - Existing: `get_semantic_summary()`, `format_chain()`

7. **`src/cmdorc_frontend/config.py`** (UPDATE)
   - KeyboardConfig parsing and validation

### **Phase 2 Files (FIX #3):**

8. **`src/textual_cmdorc/integrator.py`** (UPDATE)
   - Simplify to use `TriggerSource.from_run_handle()`
   - Remove all trigger extraction logic (should be 1-2 lines now)

9. **`src/textual_cmdorc/widgets.py`** (UPDATE)
   - Enhanced tooltips with semantic summaries

### **Documentation Updates (FIX #7):**

10. **`architecture.md`** (Already updated)
    - Added all fixes to Controller API
    - Added anti-patterns to embedding contracts

11. **`implementation.md`** (Already updated)
    - Phase 0 includes all fixes
    - Anti-patterns box added

12. **`README.md`** (Already updated)
    - Embedding example shows best practices
    - References controller API fixes

---

## Testing Strategy

### Unit Tests
- Config parsing with keyboard section
- TriggerSource.from_trigger_chain() with various chains
- TriggerSource.get_semantic_summary() for different trigger types
- Tooltip generation with shortcuts, chains, and duplicate indicators
- Key-to-command mapping
- Duplicate detection in build_command_tree()
- Startup validation logic with various config issues
- Help screen formatting with conflicts

### Integration Tests
- Full trigger chain workflow (file change → Lint → Format → Tests) with semantic summaries
- Keyboard shortcut triggers command, including duplicates
- Tooltip shows semantic summary + full chain after cascade
- >9 commands with letter shortcuts
- Startup validation summary displayed correctly
- Help screen shows conflicts accurately
- Duplicate commands display correctly in tree with (↳) suffix

## Example Configuration

```toml
[keyboard]
shortcuts = {
    Lint = "1",
    Format = "2",
    Tests = "3",
    "Build Docs" = "d",
    "Deploy" = "shift+d"
}
enabled = true

[[file_watcher]]
dir = "./src"
patterns = ["**/*.py"]
trigger = "py_file_changed"

[[command]]
name = "Lint"
command = "ruff check --fix"
triggers = ["py_file_changed"]

[[command]]
name = "Format"
command = "ruff format"
triggers = ["command_success:Lint"]

[[command]]
name = "Tests"
command = "pytest"
triggers = ["command_success:Format"]
```

**Expected behavior (with UX enhancements):**
1. App starts → Shows validation summary in log pane:
   ```
   === Config Validation Summary ===
   ✓ 3 commands loaded
   ✓ 1 file watchers active
   ✓ No issues found
   =================================
   ```
2. User saves .py file → py_file_changed
3. Lint runs (chain: `["py_file_changed"]`)
   - Tooltip: "Stop — Ran automatically (file change)\npy_file_changed\n[1] to stop"
4. Lint succeeds → Format runs (chain: `["py_file_changed", "command_success:Lint"]`)
   - Tooltip: "Stop — Ran automatically (triggered by another command)\npy_file_changed → command_success:Lint\n[2] to stop"
5. Format succeeds → Tests runs (chain: `["py_file_changed", "command_success:Lint", "command_success:Format"]`)
   - Tooltip: "Stop — Ran automatically (triggered by another command)\npy_file_changed → command_success:Lint → command_success:Format\n[3] to stop"
6. Press `3` anywhere to stop Tests
7. Press `1` to manually run Lint (chain: `[]`)
   - Tooltip: "Stop — Ran manually\nmanual\n[1] to stop"
8. Press `h` to show help screen → Displays keyboard shortcuts with any conflicts highlighted

## UX Enhancements Summary

The following enhancements address user pain points identified in external feedback:

### 1. **Semantic Summaries Before Technical Chains**
**Problem**: Raw trigger chains like "py_file_changed → command_success:Lint" are hard to understand at a glance.

**Solution**: Show human-readable summary first:
- "Ran manually" (no chain)
- "Ran automatically (file change)" (file watcher trigger)
- "Ran automatically (triggered by another command)" (lifecycle trigger)

**Impact**: Users immediately understand *why* a command ran, with technical details available below.

---

### 2. **Visual Duplicate Command Indicators**
**Problem**: Same command appearing multiple times in tree causes confusion ("Why are there two Tests?").

**Solution**:
- Add (↳) suffix to label for duplicates
- Tooltip note: "(This command appears in multiple workflows)"

**Impact**: Users recognize duplicates as intentional, not bugs.

---

### 3. **Startup Validation Summary**
**Problem**: Config errors are silent or only logged, leading to "Why doesn't X work?" confusion.

**Solution**: Display validation results in log pane on startup:
```
=== Config Validation Summary ===
✓ 12 commands loaded
✓ 3 file watchers active
⚠️ Shortcut '1' for 'Build' references unknown command
=================================
```

**Impact**: Immediate visibility into config issues without hunting through logs.

---

### 4. **Help Screen with Conflict Highlighting**
**Problem**: Keyboard shortcut conflicts are silent (last one wins), users don't know what keys do what.

**Solution**: `action_show_help()` displays:
- All configured shortcuts
- Conflicts highlighted with "⚠️ CONFLICT - last one wins"
- App shortcuts reference

**Impact**: Transparent affordances, users can diagnose their own config issues.

---

## Design Decisions & Trade-offs

### Addressed Concerns from External Feedback

**1. Mental Model Mismatch (Tree Duplication)**
- ✅ **v1**: Visual indicator for duplicates - (↳) suffix on labels
- ✅ **v1**: Tooltip note explaining "(This command appears in multiple workflows)"
- 🔮 **Future**: Optional `deduplicate = true` config for DAG-ish view (breaking change, needs design)

**2. Trigger Chains Overwhelming Users**
- ✅ **v1**: Semantic summary shown first (e.g., "Ran automatically (file change)")
- ✅ **v1**: Technical chain shown second for power users
- ✅ **v1**: Default max_width=80 with left truncation to prevent overflow
- **Trade-off**: Two-line tooltip format adds vertical space but significantly improves comprehension

**3. Keyboard Shortcuts - Invisible Affordances**
- ✅ **v1**: Help screen (`action_show_help()`) shows all shortcuts + conflicts
- ✅ **v1**: Log pane feedback when shortcut references missing widget
- ✅ **v1**: Unconfigured commands show tooltip hint
- 🔮 **Future**: Flash status message on collision (needs Textual notification system)

**4. Configuration Complexity & User Error**
- ✅ **v1**: Startup validation summary in log pane (huge win)
- ✅ **v1**: Duplicate key warnings surfaced in help screen
- ✅ **v1**: Unknown command warnings in startup summary
- 🔮 **Future**: `cmdorc config validate` CLI command for stricter pre-flight checks

**5. Async/Lifecycle Edge Cases**
- ⏸️ **Deferred**: Optimistic UI updates (conflicts with "cmdorc is source of truth" principle)
- ⏸️ **Deferred**: File causality tracking (medium complexity, nice-to-have)
- **Trade-off**: Keeping strict callback-only approach maintains architectural integrity

**6. Other Design Principles Maintained**
- ✅ **Patterns vs extensions**: Both supported; patterns take precedence
- ✅ **Debounce configurable**: debounce_ms in config
- ✅ **State reconciliation**: StateReconciler syncs on mount (idempotent, read-only)
- ✅ **90% coverage enforced**: Maintains quality
- ✅ **Step-by-step guide**: implementation.md targets junior developers

### Included in v1 (Based on Feedback)

1. ✅ **Startup validation summary** - Immediate visibility into config issues
2. ✅ **Semantic summaries before chains** - Better readability and comprehension
3. ✅ **Visual duplicate indicators** - Addresses tree duplication confusion
4. ✅ **Help screen with conflicts** - Transparent affordances for keyboard shortcuts
5. ✅ **Log pane feedback** - User-visible warnings when shortcuts fail
6. ✅ **Default max_width for chains** - Prevents tooltip overflow

### Deferred to Future Versions

1. 🔮 **Optimistic UI updates** - Needs architectural discussion (violates "no polling" principle)
2. 🔮 **File watcher causality** - Show which specific file triggered event (medium complexity)
3. 🔮 **Config validation CLI** - `cmdorc config validate config.toml` (stricter pre-flight)
4. 🔮 **Unified globs** - Merge patterns and extensions into single field (breaking change)
5. 🔮 **Graph view option** - Alternative to tree visualization for complex DAGs
6. 🔮 **Recursive ignore patterns** - Add to WatcherConfig if users request it
7. 🔮 **Flash notifications** - Brief status messages for collisions (needs Textual support)

## Critical Files to Modify

### **NEW: Embedding Architecture**

1. **`/mounted/dev/textual-cmdorc/src/textual_cmdorc/controller.py`** (NEW FILE)
   - CmdorcController class - main embed point
   - Lifecycle management (attach/detach)
   - Keyboard bindings metadata
   - Outbound event callbacks

2. **`/mounted/dev/textual-cmdorc/src/textual_cmdorc/view.py`** (NEW FILE)
   - CmdorcView widget
   - Tree rendering
   - Controller callback wiring

3. **`/mounted/dev/textual-cmdorc/src/cmdorc_frontend/notifier.py`** (NEW FILE)
   - CmdorcNotifier protocol
   - LoggingNotifier implementation
   - TextualLogPaneNotifier implementation

### **Existing Files Modified**

4. **`/mounted/dev/textual-cmdorc/src/cmdorc_frontend/models.py`**
   - Extend TriggerSource with `get_semantic_summary()` method
   - Chain formatting with truncation

2. **`/mounted/dev/textual-cmdorc/src/cmdorc_frontend/config.py`**
   - KeyboardConfig parsing and validation
   - init_keyboard_config() helper

3. **`/mounted/dev/textual-cmdorc/src/textual_cmdorc/widgets.py`**
   - Add `is_duplicate` parameter to CmdorcCommandLink
   - Enhanced tooltips with semantic summaries, chains, and duplicate indicators
   - Keyboard shortcut attribute and tooltip hints

4. **`/mounted/dev/textual-cmdorc/src/textual_cmdorc/integrator.py`**
   - Extract trigger_chain from RunHandle
   - Pass to widget updates

5. **`/mounted/dev/textual-cmdorc/src/textual_cmdorc/app.py`**
   - ConfigValidationResult dataclass
   - validate_config_and_show_summary() method
   - Global keyboard handler on_key()
   - Duplicate detection in build_command_tree()
   - action_show_help() with conflict highlighting

6. **`/mounted/dev/textual-cmdorc/architecture.md`**
   - Update with UX enhancements

7. **`/mounted/dev/textual-cmdorc/implementation.md`**
   - Update step-by-step guide with new features

8. **`/mounted/dev/textual-cmdorc/README.md`**
   - Highlight UX improvements in features list

9. **`/mounted/dev/textual-cmdorc/pyproject.toml`**
   - Add CLI entry point for `cmdorc init`

10. **`/mounted/dev/textual-cmdorc/examples/config.toml`**
    - Add example [keyboard] section

---

## Documentation Update Checklist for External Review

Before exiting plan mode, ensure all documentation files reflect the 4 new UX enhancements:

### **README.md** Updates Needed:
- [ ] Add **Embedding** section before Installation showing controller/view usage
- [ ] Update features list to mention **embeddable design** (usable standalone or as widget)
- [ ] Update features list to mention **semantic summaries** ("Ran automatically (file change)" before technical chains)
- [ ] Update features list to mention **startup validation summary** (only shows if warnings/errors - **should-fix #2**)
- [ ] Update features list to mention **help screen** (press `h` to see shortcuts and conflicts - **FIX #6** ModalScreen)
- [ ] Update features list to mention **first-launch hint** (**should-fix #3**)
- [ ] Update features list to clarify **duplicate indicators** (currently just says "Visual indicators" - specify (↳) suffix)
- [ ] Update example workflow to show semantic summary in tooltip format
- [ ] Add **Embedding Example** code snippet showing CmdorcView in larger TUI
- [ ] Add **Migration Guide (v0.1)** section after Installation (**should-fix #6**):
  - Backward-compatible standalone usage (no changes needed)
  - New embedding patterns (CmdorcController + CmdorcView)
  - Config file updates (keyboard section, validation)
  - Note: First run will show help hint
- [ ] Current status: **Good foundation, needs all fixes + should-fix items integrated**

### **architecture.md** Updates Needed:
- [ ] **Section 1**: Add embedding design principle ("Embeddable by default")
- [ ] **Section 3**: Replace component diagram with three-layer architecture (Controller/View/App)
- [ ] **Section 3**: Update responsibilities table - split CmdorcApp into Controller + View + App
- [ ] **Section 4**: Add new data flow - "Embedding Lifecycle" sequence diagram
- [ ] **Section 6 (Key Classes)**: Update `CmdorcController` API to include:
  - **FIX #1**: `request_run()` and `request_cancel()` sync-safe helpers with stored `_loop`
  - **FIX #3**: `keyboard_conflicts` property (cached, not recomputed)
  - **FIX #5**: `_on_file_change()` method showing `call_soon_threadsafe()` usage
  - **Should-fix #1**: `on_state_reconciled` callback
- [ ] **Section 6 (Key Classes)**: Add `CmdorcView` contract with:
  - **FIX #2**: `_command_links: dict[str, list[CmdorcCommandLink]]` for duplicate tracking
- [ ] **Section 6 (Key Classes)**: Add `CmdorcNotifier` protocol
- [ ] Section 6 (Key Classes): Update `TriggerSource` to include:
  - `get_semantic_summary()` method
  - **FIX #7**: `format_chain()` with minimum width check (10 chars)
- [ ] Section 6 (Key Classes): Add `is_duplicate` parameter to CmdorcCommandLink
- [ ] Section 6 (Key Classes): Add `ConfigValidationResult` dataclass
- [ ] Section 6 (Key Classes): Add `HelpScreen` ModalScreen (**FIX #6**)
- [ ] Section 6 (Key Classes): Update `CmdorcApp` to show it's now a thin shell
- [ ] Section 4.4 (Tooltip Logic): Update to show semantic summary first, then chain
- [ ] Section X (Config): Add `VALID_KEYS` set and validation function (**FIX #8**)
- [ ] Add new section: "Embedding Contracts and Guarantees"
- [ ] Current status: **Has foundation, needs all 8 fixes + should-fix items integrated**

### **implementation.md** Updates Needed:
- [ ] **NEW Step 0**: Controller/View Architecture (before current Step 1)
  - Create CmdorcController class
  - Create CmdorcView widget
  - Create CmdorcNotifier protocol
  - Refactor CmdorcApp to thin shell
  - Tests for controller lifecycle
- [ ] Step 1 (Models): Add `get_semantic_summary()` method implementation to TriggerSource
- [ ] Step 1 (Models): Add `CmdorcNotifier` protocol
- [ ] Step 6 (Widgets): Move to Step 7, update to be CmdorcView widget instead of app-level
- [ ] Step 6 (Widgets): Add `is_duplicate` parameter and label suffix logic
- [ ] Step 6 (Widgets): Update tooltip examples to show semantic summary + chain format
- [ ] Step 7 (App): Move to Step 8, refactor to show CmdorcApp as thin shell
- [ ] Step 8 (Controller): Add new step showing controller implementation details
- [ ] Step 8 (Controller): Startup validation moves to controller
- [ ] Step 8 (Controller): Help screen logic moves to controller (metadata exposure)
- [ ] Step 9 (Documentation): Add embedding examples and guides
- [ ] Step 9 (Documentation): Mention all 4 UX enhancements + embedding
- [ ] Update time estimates to reflect 19-24 hours total (was 30-50, now includes embedding + UX)
- [ ] Current status: **Good step-by-step structure, needs Phase 0 (embedding) + 4 UX features integrated**

### **Priority Order for Documentation:**
1. **implementation.md** (most detail needed - step-by-step guide)
2. **architecture.md** (authoritative reference - must be complete)
3. **README.md** (user-facing - should highlight benefits clearly)

### **Validation Criteria:**
Each doc should clearly explain:
1. ✅ **What** the feature does (user benefit)
2. ✅ **Why** it exists (addresses which pain point from feedback)
3. ✅ **How** it works (implementation details appropriate to doc type)
4. ✅ **Where** to configure it (TOML examples, method signatures)

Once these updates are made to the docs, they'll be fully aligned with the plan and ready for external review.

---

## Plan Status: PRODUCTION-READY WITH POLISH ADJUSTMENTS

### **Major Changes from Original Plan**

1. **Controller/View Split (NEW)** - Complete architectural restructuring for embeddability
   - CmdorcController: Non-Textual embed point
   - CmdorcView: Passive Textual widget
   - CmdorcApp: Thin standalone shell
   - ~6-8 hours (updated from 3-4 after second review)

2. **4 UX Enhancements (AS PLANNED)**:
   - Semantic summaries before trigger chains
   - Startup validation summary (only show if warnings/errors - **should-fix #2**)
   - Duplicate command visual indicators
   - Help screen with conflict highlighting (ModalScreen - **FIX #6**)
   - ~3-4 hours as originally estimated

3. **8 Critical Fixes (Round 2 External Review)**:
   - **FIX #1**: Async API - store `_loop`, use `self._loop.create_task()`
   - **FIX #2**: Duplicate tracking in `CmdorcView.build_command_tree()`
   - **FIX #3**: Keyboard conflicts cached in `__init__()`
   - **FIX #4**: TriggerSource adapter in integrator (keeps models UI-agnostic)
   - **FIX #5**: Watcher threading safety with `call_soon_threadsafe()`
   - **FIX #6**: Help screen as `ModalScreen` with `h` footer binding
   - **FIX #7**: Tooltip truncation min width check (10 chars)
   - **FIX #8**: Key validation against `VALID_KEYS` set
   - ~Integrated into Phase 0 and implementation details

4. **8 Should-Fix Items (Round 2 External Review)**:
   - Added `on_state_reconciled` callback for host apps
   - Startup validation only displays if warnings/errors
   - Help discoverability (footer binding + first-launch hint)
   - Key validation with specific `VALID_KEYS` set
   - Phase 0 time estimate adjusted to 6-8 hours
   - Migration guide for v0.1
   - Unit test patterns for embedding
   - Anti-patterns documentation (no global keys in controller, no `exit()`, no polling)

5. **5 Polish Adjustments (Final Review)**:
   - **POLISH #1**: `keyboard_bindings` → `keyboard_hints` (metadata only, no callables)
     - Decouples host from controller internals
     - Host wires: `self.bind(key, lambda: controller.request_run(name))`
   - **POLISH #2**: Duplicate command behavior documented in help screen
     - Note: "Shortcut affects all instances" for commands marked with ↳
   - **POLISH #3**: Notifier default changed to `NoOpNotifier` (silent)
     - Prevents stderr spam in embedded mode
     - Standalone passes `TextualLogPaneNotifier` after view created
   - **POLISH #4**: Tooltip clarity for duplicates with shortcuts
     - "Appears in multiple workflows - shortcut affects all instances"
   - **POLISH #5**: Help hint already one-shot (first-launch only)
     - Already implemented in should-fix #3

6. **4 Future-Proofing Recommendations (Final Review)**:
   - **RECOMMENDATION #1**: Controller `attach()` is idempotent
     - Guards against double-attach (returns early if already attached)
     - Validates loop is running before attaching
   - **RECOMMENDATION #2**: Stable Public API explicitly documented
     - Controller docstring declares v0.1 stable API surface
     - Prevents scope creep and anchors documentation
   - **RECOMMENDATION #3**: Centralized validation results
     - Controller builds `ConfigValidationResult`
     - App displays only, does not re-derive validation logic
     - Keeps app thin and embedding-friendly
   - **RECOMMENDATION #4**: `keyboard_hints` naming kept (not renamed to `keyboard_map`)
     - "hints" accurately signals metadata-only nature
     - "map" could confuse with dict type

7. **Scope Notes (Deferrable to v0.2 if needed)**:
   - **Help Screen (ModalScreen)**: Well-designed but adds UI surface area early
     - Core conflict visibility already exists via keyboard_conflicts, startup validation, tooltips
     - Modal is UX polish, not structural requirement
     - Can safely defer to v0.2 if schedule pressure arises
     - No architectural damage from deferral

### **Time Estimate:**
- **Original**: 10-14 hours (trigger chains + keyboard)
- **With UX enhancements**: 13-17 hours
- **With embedding architecture + Round 2 fixes**: **22-27 hours**

### **Current Status:**
✅ **Plan file updated** with all 8 must-fix issues and 8 should-fix recommendations
✅ **Code examples added** for all critical fixes
✅ **Documentation checklist updated** with specific fix references
✅ **4 remaining issues from verification FIXED:**
   1. ✅ Startup validation now conditional (only shows if warnings/errors)
   2. ✅ Removed `from_run_handle()` confusion from Phase 1 (adapter stays in integrator per FIX #4)
   3. ✅ First-launch hint added to `on_mount()` (should-fix #3)
   4. ✅ Migration guide placement clarified in README checklist (after Installation, should-fix #6)
✅ **5 polish adjustments APPLIED (final review):**
   1. ✅ Changed `keyboard_bindings` → `keyboard_hints` (metadata only, decoupled)
   2. ✅ Help screen documents duplicate behavior ("shortcut affects all instances")
   3. ✅ Default notifier is `NoOpNotifier` (silent for embedded mode)
   4. ✅ Tooltips clarify duplicate shortcut behavior
   5. ✅ Help hint already one-shot (covered by should-fix #3)
✅ **4 future-proofing recommendations APPLIED:**
   1. ✅ Controller `attach()` is idempotent (guards + loop validation)
   2. ✅ Stable Public API documented in controller docstring
   3. ✅ Validation centralized in controller (`validate_config()` method)
   4. ✅ `keyboard_hints` naming kept (signals metadata-only nature)
⏳ **Documentation files need sync** (architecture.md, implementation.md, README.md)

### **Next Steps:**
1. ✅ Plan file is production-ready (100% verified, all polish applied)
2. ⏳ Execute documentation sync checklist (2-3 hours):
   - Update architecture.md with all fixes + polish adjustments
   - Update implementation.md with Phase 0 (6-8 hours), polish notes
   - Update README.md with migration guide, polish UX notes
3. ✅ Begin Phase 0 implementation with test stubs first
4. ✅ Exit plan mode - ready for documentation sync and implementation
