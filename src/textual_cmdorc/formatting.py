"""Formatting utilities for textual-cmdorc.

Pure utility functions for formatting timestamps, output, and text.
No dependencies on app state or cmdorc internals.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def format_time_ago(timestamp: datetime | float | None) -> str:
    """Format relative timestamp.

    Args:
        timestamp: datetime object or Unix timestamp

    Returns:
        Human-readable relative time (e.g., "2s ago", "5m ago")
    """
    if not timestamp:
        return "?"

    try:
        # Handle both datetime and float timestamps
        if isinstance(timestamp, datetime):
            delta = datetime.now() - timestamp
        else:
            delta = datetime.now() - datetime.fromtimestamp(timestamp)

        seconds = delta.total_seconds()

        if seconds < 1:
            return "just now"
        elif seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        else:
            return f"{int(seconds // 86400)}d ago"

    except Exception as e:
        logger.error(f"Failed to format time ago: {e}")
        return "?"


def format_elapsed_time(start_time: float) -> str:
    """Format elapsed time from start timestamp.

    Args:
        start_time: Unix timestamp of start time

    Returns:
        Human-readable elapsed time (e.g., "2s", "5m 30s", "1h 5m")
    """
    try:
        elapsed = datetime.now().timestamp() - start_time

        if elapsed < 60:
            return f"{int(elapsed)}s"
        elif elapsed < 3600:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            return f"{hours}h {minutes}m"

    except Exception as e:
        logger.error(f"Failed to format elapsed time: {e}")
        return "?"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Args:
        text: Text potentially containing ANSI codes

    Returns:
        Text with ANSI codes removed
    """
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def get_output_preview(
    output_file: Path, max_lines: int = 5, max_line_length: int = 60
) -> tuple[list[str], int] | None:
    """Get preview of output file (last N lines).

    Args:
        output_file: Path to output file
        max_lines: Maximum number of lines to include in preview
        max_line_length: Maximum length per line before truncation

    Returns:
        (preview_lines, total_lines) if file exists, else None
    """
    try:
        with open(output_file) as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Get last N lines (or all if fewer)
        preview = lines[-max_lines:] if len(lines) > max_lines else lines

        # Strip ANSI codes and clean up
        preview = [strip_ansi(line.rstrip()) for line in preview]

        # Truncate long lines
        preview = [line[:max_line_length] + "..." if len(line) > max_line_length else line for line in preview]

        return (preview, total_lines)

    except Exception as e:
        logger.error(f"Failed to read output file {output_file}: {e}")
        return None
