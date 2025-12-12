### Design Proposal: Integrating textual-filelink.CommandLink with cmdorc.CommandConfig in textual-cmdorc

Thank you for providing the context—I've reviewed the cmdorc architecture (from `architecture.md`), README, and pyproject.toml, as well as the textual-filelink repo on GitHub. textual-filelink appears to be a specialized Textual widget library focused on "file links" that can represent actionable items like commands, with features like status indicators (e.g., pending/running/success/failed), click handlers, and visual feedback (e.g., spinners or icons). Specifically, `CommandLink` seems designed as a clickable, stateful widget for triggering and monitoring commands in a TUI.

textual-cmdorc, as an integration layer, should act as the "glue" between cmdorc (the backend orchestrator) and Textual (the frontend framework), using textual-filelink widgets as building blocks. The core requirement is to create a TUI that:

- Displays a list of configured commands (from cmdorc's `CommandConfig` list).
- Reflects real-time status (e.g., idle, running, success, failed, cancelled) based on cmdorc's execution flow.
- Allows manual run/stop via user interactions (e.g., clicks or hotkeys).
- Handles automatic triggering (via cmdorc's `TriggerEngine`) while updating the UI seamlessly.

I'll outline a **prudent, non-over-engineered design** that emphasizes separation of concerns, testability, and extensibility. This avoids god-objects or tight coupling, while being implementable with excellence (e.g., full type hints, docstrings, logging, and tests). I'll suggest minimal changes/refactors where needed, but focus on additive integration to keep things revenue-focused (i.e., quick to ship a MVP).

#### 1. High-Level Architecture
- **cmdorc**: Remains the backend. It provides `CommandOrchestrator`, `CommandConfig`, and event-driven execution. No changes needed here—it's already well-designed with swappable executors and immutable configs.
- **textual-filelink**: Provides reusable widgets like `CommandLink`. Assume `CommandLink` has props/methods like:
  - `label: str` (e.g., command name).
  - `status: Enum` (e.g., IDLE, RUNNING, SUCCESS, FAILED, CANCELLED—map to cmdorc's `RunState`).
  - `on_click: Callable` (to trigger run/cancel).
  - `update_status(state: RunState, output: str = "", duration: str = "")` (or similar; if not present, we can subclass or compose).
  - Visuals: Spinner for running, checkmark for success, etc.
  - If textual-filelink lacks direct support for cmdorc's states, a small refactor (e.g., add a `set_cmdorc_state(result: RunResult)`) could be prudent— but only if necessary; otherwise, handle mapping in textual-cmdorc.
- **textual-cmdorc**: New package (or sub-module). This is where the **pairing logic lives**. It:
  - Instantiates `CommandOrchestrator`.
  - Builds a Textual app/screen with a list of `CommandLink` widgets.
  - Maps each `CommandConfig` to a `CommandLink` instance.
  - Wires up callbacks for status updates and manual interactions.
  - Handles global TUI concerns (e.g., logging pane, trigger input).

Why put the pairing in textual-cmdorc?
- **Separation of concerns**: textual-filelink stays generic (widget-only, no cmdorc dependency). cmdorc stays backend-only. textual-cmdorc owns the integration, making it easy to swap widgets or backends later.
- **Avoids over-engineering**: No need for abstract factories or DI frameworks yet—start with simple functions/classes.
- **Testability**: Pairing logic can be unit-tested in isolation (e.g., mock `CommandOrchestrator` and assert widget props).

Potential package structure for textual-cmdorc:
```
textual-cmdorc/
├── src/
│   ├── textual_cmdorc/
│   │   ├── __init__.py
│   │   ├── app.py          # Main Textual App
│   │   ├── widgets.py      # CommandLink wrappers/adapters
│   │   ├── integrator.py   # Pairing logic (config -> widget)
│   │   └── utils.py        # Helpers (e.g., state mappers)
├── pyproject.toml          # Depends on cmdorc and textual-filelink
├── README.md
└── tests/
    └── test_integrator.py  # Tests for pairing
```

#### 2. Simple Pairing Mechanism: A Factory Function in textual-cmdorc
To keep it straightforward, use a **factory function** in `integrator.py` that takes a `CommandConfig` (or list thereof) and returns a configured `CommandLink` (or list). This is the "pairing" core— it translates cmdorc's domain (configs, triggers, states) to textual-filelink's widget settings.

```python
# src/textual_cmdorc/integrator.py
from typing import List, Optional
import logging
from cmdorc import CommandConfig, CommandOrchestrator, RunHandle, RunResult, RunState
from textual_filelink import CommandLink  # Assuming this is the widget class

logger = logging.getLogger(__name__)

def create_command_link(
    config: CommandConfig,
    orchestrator: CommandOrchestrator,
    on_status_change: Optional[Callable[[RunState, RunResult], None]] = None
) -> CommandLink:
    """
    Factory to create a CommandLink widget from a CommandConfig.
    
    :param config: The cmdorc CommandConfig to base the widget on.
    :param orchestrator: Shared orchestrator instance for running/cancelling.
    :param on_status_change: Optional callback for custom UI reactions (e.g., global log update).
    :return: A fully configured CommandLink widget.
    
    This pairs cmdorc's config with textual-filelink's widget by:
    - Setting label to config.name.
    - Wiring on_click to toggle run/cancel based on current state.
    - Registering cmdorc callbacks for status updates.
    """
    # Create the widget with initial settings
    link = CommandLink(
        label=config.name,
        tooltip=f"Triggers: {', '.join(config.triggers)}\n"
                f"Max concurrent: {config.max_concurrent}\n"
                f"Debounce: {config.debounce_in_ms}ms",
        initial_status=RunState.IDLE  # Map cmdorc.RunState to widget enum if needed
    )
    
    # Helper to update widget from cmdorc state
    def update_widget_from_result(result: RunResult):
        link.update_status(
            state=result.state,
            output=result.output,
            duration=result.duration_str,
            success=result.success,
            error=str(result.error) if result.error else ""
        )
        if on_status_change:
            on_status_change(result.state, result)
        logger.debug(f"Updated {config.name} to {result.state.value}")
    
    # Wire manual interactions (on_click handler)
    async def handle_click():
        status = orchestrator.get_status(config.name)
        if status.state == RunState.RUNNING:
            # Cancel active runs
            cancelled_count = await orchestrator.cancel_command(config.name, comment="Manual cancel from TUI")
            logger.info(f"Cancelled {cancelled_count} runs for {config.name}")
        else:
            # Run manually (fire-and-forget; status updates via callbacks)
            handle: RunHandle = await orchestrator.run_command(config.name)
            logger.info(f"Manually started {config.name} (run_id: {handle.run_id})")
    
    link.on_click = handle_click  # Assuming CommandLink has this hook
    
    # Register cmdorc lifecycle callbacks for auto-updates
    orchestrator.set_lifecycle_callback(
        config.name,
        on_success=lambda h, ctx: update_widget_from_result(h._result),  # Access internal result
        on_failed=lambda h, ctx: update_widget_from_result(h._result),
        on_cancelled=lambda h, ctx: update_widget_from_result(h._result)
    )
    # Also listen for start (via on_event for "command_started:{name}")
    orchestrator.on_event(
        f"command_started:{config.name}",
        lambda h, ctx: update_widget_from_result(h._result) if h else None
    )
    
    return link

# Convenience for lists
def create_command_links(
    configs: List[CommandConfig],
    orchestrator: CommandOrchestrator,
    on_status_change: Optional[Callable[[RunState, RunResult], None]] = None
) -> List[CommandLink]:
    return [create_command_link(c, orchestrator, on_status_change) for c in configs]
```

**Why this design?**
- **Simple and explicit**: One function call per config-widget pair. No magic (e.g., no auto-discovery).
- **Prudent extensibility**: The `on_status_change` hook allows global TUI reactions (e.g., update a log pane) without coupling.
- **Handles manual/auto**: Click toggles run/cancel; callbacks handle trigger-driven updates.
- **Maintains invariants**: Uses cmdorc's immutable `CommandConfig` directly; no mutations.
- **Logging/docstrings**: Included for clarity and debugging.
- **No over-engineering**: Starts as a function; refactor to a class (e.g., `CommandIntegrator`) if we need state (e.g., for batch operations).

#### 3. Integration in the TUI (textual-cmdorc.app.py)
The TUI app uses the factory to build its UI:

```python
# src/textual_cmdorc/app.py (excerpt)
from textual.app import App, ComposeResult
from textual.widgets import ListView, Footer, Log
from cmdorc import load_config, CommandOrchestrator
from .integrator import create_command_links

class CmdorcApp(App):
    def __init__(self, config_path: str = "cmdorc.toml"):
        super().__init__()
        self.orchestrator = CommandOrchestrator(load_config(config_path))
        self.log_pane = Log()  # For global output
    
    def compose(self) -> ComposeResult:
        # Create widgets from configs
        command_links = create_command_links(
            self.orchestrator._runtime._configs.values(),  # Access internal if needed; or use list_commands()
            self.orchestrator,
            on_status_change=self.on_global_status_change
        )
        
        yield ListView(*command_links)  # List of CommandLinks
        yield self.log_pane
        yield Footer()
    
    def on_global_status_change(self, state: RunState, result: RunResult):
        self.log_pane.write_line(f"{result.command_name}: {state.value} ({result.duration_str})")
    
    async def on_mount(self):
        # Optional: Wire global triggers (e.g., hotkey for custom events)
        pass
    
    async def shutdown(self):
        await self.orchestrator.shutdown()
```

- **Manual run/stop**: Handled via `CommandLink.on_click`.
- **Status reflection**: Cmdorc callbacks update widgets automatically.
- **Triggers**: Cmdorc handles auto-triggers; TUI can fire manual ones (e.g., via input widget: `await self.orchestrator.trigger("changes_applied")`).

#### 4. Potential Refactors and Trade-offs
- **If textual-filelink.CommandLink needs tweaks**: Add a `CmdorcAdapter` subclass in textual-cmdorc (e.g., `class CmdorcCommandLink(CommandLink)` with cmdorc-specific methods). This keeps textual-filelink clean.
- **Over-engineering pitfalls to avoid**:
  - Don't add pub/sub systems yet—cmdorc's callbacks are sufficient.
  - No async queues for updates unless polling is needed (cmdorc is event-driven).
- **Testing**: In `tests/test_integrator.py`, mock `CommandOrchestrator` and assert widget props/callbacks.
- **Changes to existing projects**:
  - textual-filelink: Minimal—perhaps add a `status_enum` if not mappable to `RunState`.
  - cmdorc: None needed; it's already excellent.
- **Revenue/pragmatism**: This gets an MVP running quickly (1-2 days). Scale to advanced features (e.g., dynamic config reload) later.