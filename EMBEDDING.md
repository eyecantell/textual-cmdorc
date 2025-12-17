# Embedding Guide: Using textual-cmdorc in Larger Applications

This guide shows how to embed textual-cmdorc's command orchestration capabilities into larger Textual applications.

**Key Principle:** textual-cmdorc is **embeddable by design**. You can use it three ways:
1. **Standalone TUI** - Just run the app (traditional usage)
2. **Widget in larger app** - Embed `CmdorcView` in your layout
3. **Headless control** - Use `CmdorcController` without any UI

---

## Table of Contents

1. [Basic Embedding Example](#basic-embedding-example)
2. [Advanced Patterns](#advanced-patterns)
3. [Real-World Scenarios](#real-world-scenarios)
4. [Event Handling](#event-handling)
5. [Keyboard Integration](#keyboard-integration)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Basic Embedding Example

### The Simplest Case: Add cmdorc to Your Sidebar

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual_cmdorc import CmdorcController, CmdorcView

class MyApp(App):
    """Larger TUI app with cmdorc command panel."""

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Layout: header, main area (sidebar + content), footer."""
        yield Header()

        # Create controller (non-Textual, reusable)
        self.cmdorc = CmdorcController("config.toml", enable_watchers=False)

        # Main layout
        yield Horizontal(
            # Command panel on the left
            CmdorcView(self.cmdorc, show_log_pane=True),

            # Your content on the right
            Vertical(
                Static("Main content area", id="content"),
            ),
        )

        yield Footer()

    async def on_mount(self):
        """Attach controller to event loop when app mounts."""
        import asyncio
        loop = asyncio.get_running_loop()

        # Controller needs to be attached to the running event loop
        self.cmdorc.attach(loop)

        # Optional: Wire controller events to your app
        self.cmdorc.on_command_finished = self.on_cmdorc_command_done

    async def on_unmount(self):
        """Clean up controller on shutdown."""
        self.cmdorc.detach()

    def on_cmdorc_command_done(self, name: str, result):
        """Handle command completion."""
        self.notify(f"✓ {name} finished: {result.state.value}")


if __name__ == "__main__":
    app = MyApp()
    app.run()
```

**Key Points:**
- `CmdorcController(config_path, enable_watchers=False)` - Host controls watcher lifecycle
- `CmdorcView(controller)` - Passive widget, just include in layout
- `controller.attach(loop)` - Attach in `on_mount()` when loop is running
- `controller.detach()` - Clean up in `on_unmount()`
- Events are callbacks (no polling)

---

## Advanced Patterns

### Pattern 1: Multiple CmdorcViews for Different Configs

Some apps have multiple independent workflows:

```python
class MultiWorkflowApp(App):
    """App with separate panels for different command sets."""

    def compose(self) -> ComposeResult:
        yield Header()

        # Load two separate configs
        self.backend_cmds = CmdorcController("config-backend.toml", enable_watchers=False)
        self.frontend_cmds = CmdorcController("config-frontend.toml", enable_watchers=False)

        yield Horizontal(
            Vertical(
                Static("Backend Commands", id="backend-label"),
                CmdorcView(self.backend_cmds, show_log_pane=False),
                id="backend-panel",
            ),
            Vertical(
                Static("Frontend Commands", id="frontend-label"),
                CmdorcView(self.frontend_cmds, show_log_pane=False),
                id="frontend-panel",
            ),
        )

        yield Footer()

    async def on_mount(self):
        import asyncio
        loop = asyncio.get_running_loop()

        # Attach both controllers
        self.backend_cmds.attach(loop)
        self.frontend_cmds.attach(loop)

    async def on_unmount(self):
        # Detach both controllers
        self.backend_cmds.detach()
        self.frontend_cmds.detach()
```

### Pattern 2: Headless Command Execution (No UI)

Sometimes you just need the orchestration logic without the TUI:

```python
import asyncio
from textual_cmdorc import CmdorcController

async def run_deployment_pipeline():
    """Execute a deployment pipeline programmatically."""

    # Create controller without rendering
    controller = CmdorcController("deploy-config.toml", enable_watchers=False)

    # Attach to event loop
    loop = asyncio.get_running_loop()
    controller.attach(loop)

    # Wire event handlers
    results = {}

    def on_command_done(name: str, result):
        results[name] = result.state.value
        print(f"✓ {name}: {result.state.value}")

    controller.on_command_finished = on_command_done

    # Run commands programmatically
    await controller.run_command("Setup")
    await asyncio.sleep(2)  # Wait for completion

    await controller.run_command("Build")
    await asyncio.sleep(3)

    await controller.run_command("Deploy")
    await asyncio.sleep(5)

    # Cleanup
    controller.detach()

    return results


# Usage
if __name__ == "__main__":
    results = asyncio.run(run_deployment_pipeline())
    print(f"Final results: {results}")
```

### Pattern 3: Custom Keyboard Binding Integration

Wire keyboard shortcuts from cmdorc config to your app:

```python
class AppWithKeyboardIntegration(App):
    """App that respects cmdorc keyboard shortcuts."""

    def compose(self) -> ComposeResult:
        yield Header()

        self.cmdorc = CmdorcController("config.toml", enable_watchers=True)
        yield CmdorcView(self.cmdorc)

        yield Footer()

    async def on_mount(self):
        import asyncio
        loop = asyncio.get_running_loop()
        self.cmdorc.attach(loop)

        # Bind cmdorc keyboard shortcuts if enabled
        if self.cmdorc.keyboard_config.enabled:
            for key, cmd_name in self.cmdorc.keyboard_hints.items():
                # Check for conflicts with app shortcuts
                if key not in ["q", "h", "r"]:  # Reserve some keys
                    self.bind(
                        key,
                        lambda name=cmd_name: self.cmdorc.request_run(name),
                        description=f"Run {cmd_name}",
                    )

            # Show help hint
            self.notify("Press 'h' for help on keyboard shortcuts")

    async def on_unmount(self):
        self.cmdorc.detach()
```

---

## Real-World Scenarios

### Scenario 1: Development Tool Dashboard

A tool that monitors and controls multiple build/test pipelines:

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane
from textual_cmdorc import CmdorcController, CmdorcView
import asyncio

class DevDashboard(App):
    """Dashboard showing multiple CI/CD pipelines."""

    TITLE = "Dev Dashboard"

    CSS = """
    Screen {
        layout: vertical;
    }

    #pipeline-tabs {
        height: 1fr;
    }

    TabPane {
        border: solid $primary;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()

        # Create controller for each pipeline
        self.lint_pipeline = CmdorcController("pipelines/lint.toml", enable_watchers=False)
        self.test_pipeline = CmdorcController("pipelines/test.toml", enable_watchers=False)
        self.build_pipeline = CmdorcController("pipelines/build.toml", enable_watchers=False)

        with TabbedContent(id="pipeline-tabs"):
            with TabPane("Lint", id="lint-tab"):
                yield CmdorcView(self.lint_pipeline, show_log_pane=True)

            with TabPane("Test", id="test-tab"):
                yield CmdorcView(self.test_pipeline, show_log_pane=True)

            with TabPane("Build", id="build-tab"):
                yield CmdorcView(self.build_pipeline, show_log_pane=True)

        yield Footer()

    async def on_mount(self):
        loop = asyncio.get_running_loop()

        # Attach all pipelines
        for controller in [self.lint_pipeline, self.test_pipeline, self.build_pipeline]:
            controller.attach(loop)
            controller.on_command_finished = self.on_any_pipeline_done
            controller.on_validation_result = self.on_any_validation

    async def on_unmount(self):
        # Cleanup all pipelines
        for controller in [self.lint_pipeline, self.test_pipeline, self.build_pipeline]:
            controller.detach()

    def on_any_pipeline_done(self, name: str, result):
        """Handle pipeline command completion."""
        self.notify(f"Pipeline update: {name} → {result.state.value}")

    def on_any_validation(self, result):
        """Handle validation results."""
        if result.errors:
            self.notify(f"⚠️ {len(result.errors)} config errors", severity="warning")


if __name__ == "__main__":
    app = DevDashboard()
    app.run()
```

### Scenario 2: Deploy Control Center

An app for managing production deployments with safety checks:

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button
from textual.reactive import reactive
from textual_cmdorc import CmdorcController, CmdorcView

class DeployCenter(App):
    """Control center for managing deployments."""

    deployment_status = reactive("Ready")

    CSS = """
    Screen {
        layout: vertical;
    }

    #deploy-area {
        height: 1fr;
    }

    #status-bar {
        background: $primary;
        color: $text;
        padding: 1 2;
    }

    Button {
        margin: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()

        self.deploy_controller = CmdorcController(
            "deployments.toml",
            enable_watchers=False
        )

        yield Horizontal(
            CmdorcView(self.deploy_controller, show_log_pane=True),
            Vertical(
                Static("Deployment Controls", id="controls-header"),
                Button("Deploy to Staging", id="deploy-staging", variant="primary"),
                Button("Deploy to Production", id="deploy-prod", variant="warning"),
                Button("Rollback", id="rollback", variant="error"),
                Button("Health Check", id="health-check", variant="primary"),
                id="controls-panel",
            ),
            id="deploy-area",
        )

        yield Static(self.deployment_status, id="status-bar")
        yield Footer()

    async def on_mount(self):
        import asyncio
        loop = asyncio.get_running_loop()

        self.deploy_controller.attach(loop)
        self.deploy_controller.on_command_finished = self.on_deploy_done
        self.deploy_controller.on_validation_result = self.on_deploy_validation

    async def on_unmount(self):
        self.deploy_controller.detach()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        button_id = event.button.id

        if button_id == "deploy-staging":
            self.deployment_status = "Deploying to Staging..."
            self.deploy_controller.request_run("DeployStaging")

        elif button_id == "deploy-prod":
            # Safety: Require confirmation
            self.notify("Production deploy initiated", severity="warning")
            self.deployment_status = "Deploying to Production..."
            self.deploy_controller.request_run("DeployProduction")

        elif button_id == "rollback":
            self.deployment_status = "Rolling back..."
            self.deploy_controller.request_run("Rollback")

        elif button_id == "health-check":
            self.deployment_status = "Running health checks..."
            self.deploy_controller.request_run("HealthCheck")

    def on_deploy_done(self, name: str, result):
        """Handle deployment completion."""
        status_emoji = "✓" if result.state.value == "success" else "✗"
        self.deployment_status = f"{status_emoji} {name} → {result.state.value}"

        if result.state.value == "success":
            self.notify(f"✓ {name} succeeded")
        else:
            self.notify(f"✗ {name} failed", severity="error")

    def on_deploy_validation(self, result):
        """Validate deployment config on startup."""
        if result.errors:
            self.deployment_status = f"⚠️ Config errors: {len(result.errors)}"
            for error in result.errors:
                self.notify(error, severity="error")


if __name__ == "__main__":
    app = DeployCenter()
    app.run()
```

---

## Event Handling

### Available Callbacks

The `CmdorcController` exposes these callback properties:

```python
controller = CmdorcController("config.toml", enable_watchers=False)

# Command lifecycle
controller.on_command_started = lambda name, trigger: print(f"Started: {name}")
controller.on_command_finished = lambda name, result: print(f"Finished: {name}")

# Validation
controller.on_validation_result = lambda result: print(f"Validation: {result.warnings}")

# State reconciliation (on startup)
controller.on_state_reconciled = lambda name, state: print(f"Reconciled: {name}")

# Intent signals (host app should handle)
controller.on_quit_requested = lambda: print("Quit requested")
controller.on_cancel_all_requested = lambda: print("Cancel all requested")
```

### Example: Status Aggregation

```python
class StatusAggregator:
    """Track overall status across multiple commands."""

    def __init__(self, controller):
        self.controller = controller
        self.running = set()
        self.failed = set()
        self.completed = set()

        controller.on_command_started = self._on_started
        controller.on_command_finished = self._on_finished

    def _on_started(self, name, trigger):
        self.running.add(name)
        self.failed.discard(name)
        self.completed.discard(name)

    def _on_finished(self, name, result):
        self.running.discard(name)
        if result.state.value == "success":
            self.completed.add(name)
        else:
            self.failed.add(name)

    def get_summary(self):
        return {
            "running": len(self.running),
            "completed": len(self.completed),
            "failed": len(self.failed),
        }
```

---

## Keyboard Integration

### Using keyboard_hints Safely

```python
# Option 1: Host app binds shortcuts from controller metadata
controller = CmdorcController("config.toml", enable_watchers=False)

# Check conflicts before binding
conflicts = controller.keyboard_conflicts
reserved_keys = {"q", "h", "r", "l"}  # Your app's reserved keys

for key, cmd_name in controller.keyboard_hints.items():
    if key not in conflicts and key not in reserved_keys:
        app.bind(
            key,
            lambda name=cmd_name: controller.request_run(name),
            description=f"Run: {cmd_name}",
        )

# Option 2: Use controller's request_run for sync-safe execution
def handle_key(event):
    if event.key == "1":
        controller.request_run("Lint")  # Safe to call from UI context
```

---

## Best Practices

### 1. Always Use `enable_watchers=False` in Embedded Mode

```python
# ✓ Correct: Host controls watcher lifecycle
controller = CmdorcController("config.toml", enable_watchers=False)

# ✗ Wrong: Conflicting watcher startup
controller = CmdorcController("config.toml", enable_watchers=True)
```

### 2. Attach Controller in `on_mount()`, Detach in `on_unmount()`

```python
async def on_mount(self):
    import asyncio
    loop = asyncio.get_running_loop()
    self.controller.attach(loop)  # Loop must be running

async def on_unmount(self):
    self.controller.detach()  # Clean shutdown
```

### 3. Use Sync-Safe Methods from UI Callbacks

```python
# ✓ Correct: Use sync-safe request_run
def on_button_clicked(self):
    self.controller.request_run("CommandName")

# ✗ Wrong: Async method in sync callback
def on_button_clicked(self):
    asyncio.create_task(self.controller.run_command("CommandName"))
```

### 4. Wire Callbacks, Don't Poll

```python
# ✓ Correct: Event-driven
controller.on_command_finished = self.on_cmd_done

# ✗ Wrong: Polling orchestrator state
while True:
    state = controller.orchestrator.get_state()
    # ...
    await asyncio.sleep(0.5)
```

### 5. Validate Configuration Early

```python
async def on_mount(self):
    self.controller.attach(loop)

    # Get validation results
    result = self.controller.validate_config()

    if result.errors:
        for error in result.errors:
            self.notify(f"Config error: {error}", severity="error")

    if result.warnings:
        for warning in result.warnings:
            self.notify(f"Warning: {warning}")
```

### 6. Check Keyboard Conflicts Before Binding

```python
# Get both hints and conflicts
hints = self.controller.keyboard_hints
conflicts = self.controller.keyboard_conflicts

for key, cmd_name in hints.items():
    if key in conflicts:
        self.notify(f"⚠️ Key {key} has conflicts: {conflicts[key]}")
    else:
        self.bind(key, lambda n=cmd_name: self.controller.request_run(n))
```

---

## Troubleshooting

### Issue: "Controller not attached to event loop"

**Cause:** Called `request_run()` before `attach()` or outside async context.

**Solution:**
```python
# ✓ Correct
async def on_mount(self):
    loop = asyncio.get_running_loop()
    self.controller.attach(loop)  # Attach first

    # Now safe to use
    self.controller.request_run("Cmd")

# ✗ Wrong
controller = CmdorcController(...)
controller.request_run("Cmd")  # attach() not called yet
```

### Issue: Commands Don't Run After Detach

**Cause:** `detach()` cancels all running commands and stops watchers.

**Solution:** Don't call `detach()` until you're truly shutting down.

```python
async def on_unmount(self):
    # Cancel any running commands first if needed
    # for cmd in self.controller.hierarchy:
    #     await self.controller.cancel_command(cmd.name)

    # Then detach
    self.controller.detach()
```

### Issue: Duplicate Keyboard Bindings

**Cause:** Multiple views or app-level bindings competing for same key.

**Solution:** Check `keyboard_conflicts` before binding.

```python
conflicts = self.controller.keyboard_conflicts
if key not in conflicts:
    app.bind(key, ...)
else:
    logger.warning(f"Key {key} conflicts: {conflicts[key]}")
```

### Issue: File Watchers Not Triggering

**Cause:** `enable_watchers=False` or directory doesn't exist.

**Solution:**
```python
# Validate config on startup
result = controller.validate_config()
for warning in result.warnings:
    if "watch" in warning.lower() or "file" in warning.lower():
        logger.warning(f"Watcher issue: {warning}")
```

---

## Summary

textual-cmdorc is designed to be embedded easily:

1. **Create controller** - Non-Textual, reusable orchestration logic
2. **Create view(s)** - Passive widgets, include in your layout
3. **Attach on mount** - Connect to event loop
4. **Wire callbacks** - React to command events
5. **Detach on unmount** - Clean shutdown
6. **Use sync-safe methods** - `request_run()` / `request_cancel()` from UI

For questions or issues, see [architecture.md](architecture.md#65-embedding-architecture--contracts) for detailed contracts and guarantees.
