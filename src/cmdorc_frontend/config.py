"""Configuration parsing for cmdorc frontend."""

from pathlib import Path
from typing import Tuple
import logging

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from cmdorc import load_config, RunnerConfig
from cmdorc_frontend.models import CommandNode, KeyboardConfig
from cmdorc_frontend.watchers import WatcherConfig

logger = logging.getLogger(__name__)


def load_frontend_config(
    path: str | Path,
) -> Tuple[RunnerConfig, KeyboardConfig, list[WatcherConfig], list[CommandNode]]:
    """Load configuration for any frontend.

    Args:
        path: Path to TOML config file

    Returns:
        Tuple of (runner_config, keyboard_config, watchers, hierarchy)
    """
    path = Path(path)

    # Load TOML content
    with open(path) as f:
        raw = tomllib.loads(f.read())

    # Parse keyboard config (FIX #8: validation happens in controller)
    keyboard_raw = raw.get("keyboard", {})
    keyboard_config = KeyboardConfig(
        shortcuts=keyboard_raw.get("shortcuts", {}),
        enabled=keyboard_raw.get("enabled", True),
        show_in_tooltips=keyboard_raw.get("show_in_tooltips", True),
    )

    # Parse watchers
    watchers = [
        WatcherConfig(
            dir=path.parent / Path(w["dir"]),
            patterns=w.get("patterns"),
            extensions=w.get("extensions"),
            ignore_dirs=w.get("ignore_dirs", ["__pycache__", ".git"]),
            trigger=w["trigger"],
            debounce_ms=w.get("debounce_ms", 300),
        )
        for w in raw.get("file_watcher", [])
    ]

    # Use cmdorc's loader for runner config
    runner_config = load_config(path)

    # Build hierarchy from runner config
    from cmdorc import CommandConfig
    from typing import Dict, List
    import re

    commands: Dict[str, CommandConfig] = {c.name: c for c in runner_config.commands}
    graph: Dict[str, List[str]] = {name: [] for name in commands}

    for name, config in commands.items():
        for trigger in config.triggers:
            match = re.match(r"(command_success|command_failed|command_cancelled):(.+)", trigger)
            if match:
                trigger_type, parent = match.groups()
                if parent in graph:
                    graph[parent].append(name)

    visited: set[str] = set()
    roots: List[CommandNode] = []

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

    return runner_config, keyboard_config, watchers, roots
