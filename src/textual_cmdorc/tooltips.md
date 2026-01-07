# Tooltip Design Specification

This document defines the tooltip content and behavior for all interactive elements in textual-cmdorc.

## Overview

textual-cmdorc uses tooltips to provide rich contextual information without cluttering the UI. Each `CommandLink` widget has multiple interactive elements, each with its own tooltip strategy.

## Design Principles

1. **Context-Aware**: Tooltips adapt based on command state (idle, running, completed)
2. **Actionable**: Always include keyboard shortcuts for interactive elements
3. **Purpose-Aligned**: Group related information by element purpose
   - **Status icon**: Run history and results
   - **Play/Stop button**: Trigger conditions and command preview
   - **Command name**: Output file access and preview
4. **Informative**: Show history, trigger chains, and downstream effects
5. **Concise**: Limit to most relevant information (e.g., last 3 runs, 5 output lines)

## Tooltip Hierarchy

### 1. Status Icon Tooltip (◯/⏳/✅/❌/⚠️)

The leftmost icon shows command state. Tooltip shows **run history and results**.

#### Idle State (◯ - Not Yet Run)

```
Lint
────
◯ Not yet run
```

**Content:**
- Command name (header)
- Separator line
- Status: "◯ Not yet run"

**Simple and clear**: No history yet, status is self-explanatory.

#### Running State (⏳ - In Progress)

```
Lint
────
⏳ Running for 2m 14s

Command: ruff check --fix .
```

**Content:**
- Command name (header)
- Separator line
- Elapsed time (updates on re-hover)
- Resolved command preview

**Formatting Rules:**
- Elapsed time: "Xs", "Xm Ys", "Xh Ym" format
- Command preview: Full resolved command string

#### Completed State (✅/❌/⚠️ - Success/Failed/Cancelled)

```
Tests
─────
Last 3 runs:
  ✅ 2s ago for 1.2s
  ✅ 5m ago for 1.1s
  ❌ 12m ago for 0.9s (exit 1)

Command: pytest ./tests -v
```

**Content:**
- Command name (header)
- Separator line
- Last 3 runs (status, time ago, duration, exit code)
- Resolved command preview

**Formatting Rules:**
- History: Use `orchestrator.get_history(cmd_name, limit=3)`
- Format: `{icon} {time_ago} for {duration} (exit {code})`
- Time ago: "Xs ago", "Xm ago", "Xh ago", "Xd ago"
- Exit codes: Show only for FAILED state
- No "Last run:" prefix if only 1 run (just show the run)

**Single Run (No History):**
```
Tests
─────
Last run:
  ✅ 2s ago for 1.2s

Command: pytest ./tests -v
```

### 2. Play/Stop Button Tooltip (▶️/⏹️)

The play/stop button controls execution. Tooltip shows **why/when this would run**.

#### Play Button (▶️ - Idle State)

```
▶️ Run Lint

Command: ruff check --fix .

Triggers:
  • py_file_changed
  • After Format succeeds
  • [1] manual

On success →
  → Format
  → Tests

On failure →
  → Notify

Cancel on:
  • prompt_send
  • exit
```

**Content:**
- Action header: "▶️ Run {command_name}"
- Resolved command preview
- Trigger sources (semantic formatting)
- Keyboard shortcut (if configured)
- Downstream commands (success chain)
- Downstream commands (failure chain, if configured)
- Cancel triggers (if configured)

**Formatting Rules:**
- Trigger `command_success:X` → "After X succeeds"
- Trigger `command_failed:X` → "After X fails"
- Other triggers → Show as-is
- Limit downstream to 3 commands per chain, add "... and N more" if truncated
- Omit sections with no content (e.g., no failure chain, no cancel triggers)

#### Stop Button (⏹️ - Running State)

```
⏹️ Stop Lint

Running for 2m 14s

Command: ruff check --fix .

Trigger: Ran manually

Chain:
  user_saves → command_started:Lint

[1] to stop
```

**Content:**
- Action header: "⏹️ Stop {command_name}"
- Elapsed time
- Resolved command preview
- Semantic trigger summary (from TriggerSource)
- Full trigger chain (if multiple hops)
- Keyboard shortcut to stop

**Formatting Rules:**
- Elapsed time: "Xs", "Xm Ys", "Xh Ym" format
- Show chain only if `len(trigger_chain) > 1`
- Use TriggerSource.format_chain() for consistent formatting

### 3. Command Name Tooltip (Clickable Text)

The command name is clickable and opens the output file. Tooltip shows **output access**.

#### No Output Available

```
Lint

No output available yet
```

**Content:**
- Command name (header)
- Message: "No output available yet"

**Simple**: Command hasn't run or output_storage disabled.

#### Output Available

```
Lint

Open: .cmdorc/outputs/Lint/run-abc123/output.txt

Last 5 lines:
────────────────────────────────────────
All checks passed! ✅
24 files checked
0 errors found
0 warnings found
Completed in 1.2s
────────────────────────────────────────

Click to open in editor
```

**Content:**
- Command name (header)
- Output file path (full absolute path)
- Last 5 lines of output (if output ≤ 5 lines, show all)
- Separator lines for visual clarity
- Action hint: "Click to open in editor"

**Formatting Rules:**
- **Show preview only if**: `len(output_lines) <= 5`
- **Always show**: Last 5 lines (tail behavior)
- **ANSI colors**: Textual supports Rich markup, but terminal ANSI codes need stripping/conversion
- **Long lines**: Truncate to ~60 chars with "..." if needed
- **Empty output**: Show "(empty output)" instead of preview

**Alternative (Output > 5 lines):**
```
Lint

Open: .cmdorc/outputs/Lint/run-abc123/output.txt

[242 lines - click to open in editor]
```

**Rationale:**
- 5-line limit prevents overwhelming tooltips
- Last 5 lines most relevant (final status, error messages)
- Full path helps users locate file manually if needed

### 4. Settings Icon Tooltip (⚙️)

**Placeholder for future functionality:**

```
Settings (s)

Command configuration
(coming soon)
```

**Content:**
- Currently shows action hint
- Future: Command configuration preview

## Technical Implementation

### Helper Methods

#### `_get_command_string(cmd_name: str) -> str`
```python
def _get_command_string(self, cmd_name: str) -> str:
    """Get resolved command string using preview_command()."""
    preview = self.adapter.orchestrator.preview_command(cmd_name)
    return preview.command
```

#### `_get_downstream_commands(cmd_name: str, trigger_type: str) -> list[str]`
```python
def _get_downstream_commands(self, cmd_name: str, trigger_type: str = "success") -> list[str]:
    """Get commands triggered after success/failure.
    
    Args:
        cmd_name: Command name
        trigger_type: "success" or "failure"
    """
    trigger_graph = self.adapter.orchestrator.get_trigger_graph()
    trigger_key = f"command_{trigger_type}:{cmd_name}"
    return trigger_graph.get(trigger_key, [])
```

#### `_format_time_ago(timestamp) -> str`
```python
def _format_time_ago(self, timestamp) -> str:
    """Format relative timestamp: '2s ago', '5m ago', etc."""
    # Handles both datetime and float timestamps
    # Returns: "just now", "Xs ago", "Xm ago", "Xh ago", "Xd ago"
```

#### `_get_output_preview(cmd_name: str) -> tuple[str, list[str]] | None`
```python
def _get_output_preview(self, cmd_name: str) -> tuple[str, list[str]] | None:
    """Get output file path and preview (last 5 lines).
    
    Returns:
        (file_path, preview_lines) if output available, else None
    """
    # Get latest run handle/result
    status = self.adapter.orchestrator.get_status(cmd_name)
    if not status.latest_result or not status.latest_result.output_file:
        return None
    
    output_file = status.latest_result.output_file
    
    # Read output file
    try:
        with open(output_file) as f:
            lines = f.readlines()
        
        # Get last 5 lines
        preview = lines[-5:] if len(lines) > 5 else lines
        
        # Strip ANSI codes (optional - or convert to Rich markup)
        preview = [strip_ansi(line.rstrip()) for line in preview]
        
        return (str(output_file), preview)
    except Exception as e:
        logger.error(f"Failed to read output: {e}")
        return None
```

### ANSI Handling

Textual supports Rich markup in tooltips. Two options for ANSI codes:

**Option 1: Strip ANSI (Simple)**
```python
import re

def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)
```

**Option 2: Convert ANSI to Rich (Prettier)**
```python
from rich.console import Console
from io import StringIO

def ansi_to_rich(text: str) -> str:
    """Convert ANSI codes to Rich markup."""
    console = Console(file=StringIO(), force_terminal=True, legacy_windows=False)
    # Rich can parse ANSI and convert to markup
    # This requires more investigation into Rich's ANSI parsing
    return text  # Placeholder
```

**Recommendation**: Start with Option 1 (strip ANSI) for MVP, add Option 2 later if needed.

### State Transitions

Tooltips update automatically on state changes:

1. **Command Start**: 
   - Status icon → Running tooltip (with elapsed time + command)
   - Play button → Becomes stop button (with trigger info)

2. **Command Complete**:
   - Status icon → Result tooltip (with history + command)
   - Stop button → Becomes play button (with trigger/downstream info)
   - Command name → Shows output preview (if available)

3. **Config Reload**:
   - All tooltips rebuilt from scratch
   - History preserved (loaded from disk if output_storage enabled)

## Configuration

### Keyboard Shortcuts

Shortcuts are included in play/stop tooltips:

```toml
[keyboard]
shortcuts = { Lint = "1", Format = "2", Tests = "3" }
enabled = true
show_in_tooltips = true
```

### History Display

Status icon tooltip respects `keep_in_memory` setting:

```toml
[[command]]
name = "Tests"
keep_in_memory = 3  # Shows last 3 runs in status tooltip
```

### Output Storage

Enable output_storage for output preview:

```toml
[output_storage]
directory = ".cmdorc/outputs"
keep_history = 10
```

Without output_storage, command name tooltip shows "No output available yet".

## Edge Cases

### No History Available
- Status icon: Shows "◯ Not yet run" (idle) or single run info
- No "Last 3 runs:" section

### No Downstream Commands
- Play button: Omit "On success →" section
- Keeps tooltip concise

### No Cancel Triggers
- Play button: Omit "Cancel on:" section

### Output > 5 Lines
- Command name: Show line count + "click to open"
- No preview section

### Empty Output
- Command name: Show "(empty output)" in preview

### Long Output Lines
- Truncate to ~60 chars with "..."
- Full lines available in editor

### ANSI Escape Codes
- Strip before displaying (MVP)
- Or convert to Rich markup (future enhancement)

## Tooltip Summary Table

| Element | Purpose | Content Focus |
|---------|---------|---------------|
| **Status Icon** | Show history | Last 3 runs + command preview |
| **Play Button** | Show trigger conditions | Triggers, downstream, cancel_on |
| **Stop Button** | Show run context | Elapsed time, trigger chain, command |
| **Command Name** | Access output | File path + last 5 lines preview |
| **Settings** | Future config | Placeholder |

## Testing Tooltips

### Manual Testing
1. **Status Icon**: 
   - Idle → "Not yet run"
   - Running → Elapsed time updates on re-hover
   - Complete → Shows last 3 runs with "for" duration

2. **Play Button**:
   - Shows all trigger sources
   - Shows downstream chains (success + failure)
   - Shows cancel triggers

3. **Stop Button**:
   - Shows elapsed time
   - Shows trigger chain that started this run
   - Updates every time tooltip re-opens

4. **Command Name**:
   - No output → "No output available yet"
   - Short output (≤5 lines) → Full preview
   - Long output (>5 lines) → Line count + hint

### Automated Testing
```python
def test_status_icon_history():
    tooltip = app._build_status_tooltip("Tests", handle)
    assert "Last 3 runs:" in tooltip
    assert "for 1.2s" in tooltip  # Duration format

def test_play_button_triggers():
    tooltip = app._build_play_tooltip("Lint")
    assert "Triggers:" in tooltip
    assert "On success →" in tooltip
    
def test_stop_button_elapsed():
    tooltip = app._build_stop_tooltip("Lint", handle)
    assert "Running for" in tooltip
    assert "Trigger:" in tooltip

def test_output_preview_short():
    tooltip = app._build_output_tooltip("Tests")
    assert "Last 5 lines:" in tooltip
    assert "Click to open" in tooltip

def test_output_preview_long():
    tooltip = app._build_output_tooltip("Build")
    assert "[242 lines" in tooltip
    assert "click to open" in tooltip
```

## Future Enhancements

### Settings Tooltip
Show command configuration:
```
Settings (s)
────────────────
Command: ruff check --fix .
Working dir: /home/user/project
Timeout: 300s
Max concurrent: 1
Debounce: 500ms
```

### Configurable Preview Length
```toml
[ui]
output_preview_lines = 5  # Default
output_preview_chars = 60  # Line truncation
```

### Rich ANSI Conversion
Convert ANSI codes to Rich markup for colored output preview.

### Trigger Chain Visualization
Add tree diagram for complex chains (future enhancement).

## References

- **textual-filelink**: CommandLink API for tooltip methods
- **cmdorc**: get_trigger_graph(), get_history(), preview_command()
- **TriggerSource**: Semantic formatting and chain display (cmdorc_frontend.models)
- **Rich**: ANSI parsing and markup conversion