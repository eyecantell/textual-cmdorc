"""Configuration parsing for cmdorc frontend."""

import logging
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from cmdorc import RunnerConfig, load_config
from textual_filelink import FileLink

from cmdorc_frontend.models import CommandNode, EditorConfig, KeyboardConfig
from cmdorc_frontend.watchers import WatcherConfig

logger = logging.getLogger(__name__)


def load_merged_frontend_config(
    paths: list[Path],
) -> tuple[KeyboardConfig, list[WatcherConfig], EditorConfig]:
    """Load and merge frontend config from multiple files.

    Merges keyboard shortcuts (later files override earlier), editor config
    (later files override earlier), and concatenates watchers.

    Override behavior:
    - Keyboard shortcuts: Later files override earlier files (per-key basis)
    - Editor template: Later files completely replace earlier template
    - Watchers: Concatenated (all watchers from all files are active)

    Args:
        paths: List of config file paths

    Returns:
        Tuple of (merged_keyboard_config, merged_watchers, merged_editor_config)
    """
    merged_shortcuts: dict[str, str] = {}
    keyboard_enabled = True
    show_in_tooltips = True
    merged_command_template = FileLink.VSCODE_TEMPLATE
    all_watchers: list[WatcherConfig] = []

    for path in paths:
        if not path.exists():
            logger.warning(f"Config file not found, skipping: {path}")
            continue

        try:
            with open(path) as f:
                raw = tomllib.loads(f.read())
        except Exception as e:
            logger.warning(f"Failed to parse {path}: {e}")
            continue

        # Merge keyboard config (later files override)
        keyboard_raw = raw.get("keyboard", {})
        if "shortcuts" in keyboard_raw:
            new_shortcuts = keyboard_raw["shortcuts"]
            overlapping = set(merged_shortcuts.keys()) & set(new_shortcuts.keys())
            if overlapping:
                logger.debug(f"Keyboard shortcuts overridden by {path.name}: {overlapping}")
            merged_shortcuts.update(new_shortcuts)
        if "enabled" in keyboard_raw:
            keyboard_enabled = keyboard_raw["enabled"]
        if "show_in_tooltips" in keyboard_raw:
            show_in_tooltips = keyboard_raw["show_in_tooltips"]

        # Merge editor config (later files override)
        editor_raw = raw.get("editor", {})
        if "command_template" in editor_raw:
            template = editor_raw["command_template"]
            if template:  # Only override if not empty
                if merged_command_template != FileLink.VSCODE_TEMPLATE:
                    # Not the default, so we're overriding a previous config
                    logger.debug(f"Editor template overridden by {path.name}")
                merged_command_template = template

        # Concatenate watchers
        for w in raw.get("file_watcher", []):
            all_watchers.append(
                WatcherConfig(
                    dir=path.parent / Path(w["dir"]),
                    extensions=w.get("extensions"),
                    ignore_dirs=w.get("ignore_dirs", ["__pycache__", ".git"]),
                    trigger_emitted=w["trigger_emitted"],
                    debounce_ms=w.get("debounce_ms", 300),
                    recursive=w.get("recursive", True),
                )
            )

    keyboard_config = KeyboardConfig(
        shortcuts=merged_shortcuts,
        enabled=keyboard_enabled,
        show_in_tooltips=show_in_tooltips,
    )

    editor_config = EditorConfig(command_template=merged_command_template)

    return keyboard_config, all_watchers, editor_config


def load_frontend_config(
    path: str | Path,
) -> tuple[RunnerConfig, KeyboardConfig, list[WatcherConfig], list[CommandNode], EditorConfig]:
    """Load configuration for any frontend.

    Args:
        path: Path to TOML config file

    Returns:
        Tuple of (runner_config, keyboard_config, watchers, hierarchy, editor_config)
    """
    path = Path(path)

    # Check file exists with helpful error
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\nRun 'cmdorc-tui' without arguments to auto-create a default config."
        )

    # Load TOML content
    try:
        with open(path) as f:
            raw = tomllib.loads(f.read())
    except Exception as e:
        raise ValueError(f"Failed to parse config file {path}: {e}") from e

    # Parse keyboard config (validation happens in orchestrator adapter)
    keyboard_raw = raw.get("keyboard", {})
    keyboard_config = KeyboardConfig(
        shortcuts=keyboard_raw.get("shortcuts", {}),
        enabled=keyboard_raw.get("enabled", True),
        show_in_tooltips=keyboard_raw.get("show_in_tooltips", True),
    )

    # Parse editor config
    editor_raw = raw.get("editor", {})
    template = editor_raw.get("command_template", "")
    editor_config = EditorConfig(
        command_template=template if template else FileLink.VSCODE_TEMPLATE  # Handle empty string
    )

    # Parse watchers
    watchers = [
        WatcherConfig(
            dir=path.parent / Path(w["dir"]),
            extensions=w.get("extensions"),
            ignore_dirs=w.get("ignore_dirs", ["__pycache__", ".git"]),
            trigger_emitted=w["trigger_emitted"],
            debounce_ms=w.get("debounce_ms", 300),
            recursive=w.get("recursive", True),
        )
        for w in raw.get("file_watcher", [])
    ]

    # Use cmdorc's loader for runner config
    runner_config = load_config(path)

    # Build hierarchy from runner config
    import re

    from cmdorc import CommandConfig

    commands: dict[str, CommandConfig] = {c.name: c for c in runner_config.commands}
    graph: dict[str, list[str]] = {name: [] for name in commands}

    for name, config in commands.items():
        for trigger in config.triggers:
            match = re.match(r"(command_success|command_failed|command_cancelled):(.+)", trigger)
            if match:
                trigger_type, parent = match.groups()
                if parent in graph:
                    graph[parent].append(name)

    visited: set[str] = set()
    roots: list[CommandNode] = []

    def build_node(name: str, visited_local: set[str]) -> CommandNode | None:
        if name in visited_local:
            logger.warning(f"Cycle detected at {name}, skipping duplicate")
            return None
        visited_local.add(name)
        node = CommandNode(config=commands[name])
        for child_name in graph.get(name, []):
            child_node = build_node(child_name, visited_local.copy())
            if child_node:
                node.children.append(child_node)
        return node

    all_children = {c for children in graph.values() for c in children}
    potential_roots = [name for name in commands if name not in all_children]

    for root_name in potential_roots:
        if root_name not in visited:
            root_node = build_node(root_name, set())
            if root_node:
                roots.append(root_node)
                visited.add(root_name)

    return runner_config, keyboard_config, watchers, roots, editor_config
