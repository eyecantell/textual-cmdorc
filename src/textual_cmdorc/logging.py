"""Logging utilities for textual-cmdorc.

Provides coordinated logging setup for textual-cmdorc, cmdorc, and textual-filelink.

Usage:
    # Silent by default (production)
    # Nothing needed - NullHandler is set by default

    # Enable file logging for debugging
    from textual_cmdorc import setup_logging
    setup_logging()  # Logs to .cmdorc/logs/cmdorc-tui.log

    # Enable all packages (for debugging dependencies)
    setup_logging(log_all=True)

    # Disable all logging
    from textual_cmdorc import disable_logging
    disable_logging()
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Literal

# Package namespaces to configure
TEXTUAL_CMDORC_NAMESPACE = "textual_cmdorc"
CMDORC_FRONTEND_NAMESPACE = "cmdorc_frontend"

# External package namespaces (for --log-all)
CMDORC_NAMESPACE = "cmdorc"
TEXTUAL_FILELINK_NAMESPACE = "textual_filelink"

# Default log location (project-relative)
DEFAULT_LOG_DIR = Path(".cmdorc") / "logs"
DEFAULT_LOG_FILENAME = "cmdorc-tui.log"

# Format strings
SIMPLE_FORMAT = "%(levelname)s:%(name)s:%(message)s"
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"


def get_log_file_path(
    log_dir: Path | str = DEFAULT_LOG_DIR,
    log_filename: str = DEFAULT_LOG_FILENAME,
) -> Path:
    """Get the full path to the log file.

    Args:
        log_dir: Directory for log files
        log_filename: Name of the log file

    Returns:
        Full path to the log file
    """
    log_dir = Path(log_dir)
    return log_dir / log_filename


def setup_logging(
    level: int | str = logging.DEBUG,
    *,
    log_dir: Path | str = DEFAULT_LOG_DIR,
    log_filename: str = DEFAULT_LOG_FILENAME,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    format: Literal["simple", "detailed"] = "detailed",
    format_string: str | None = None,
    log_all: bool = False,
) -> logging.Logger:
    """Configure logging for textual-cmdorc and optionally related packages.

    By default, only textual-cmdorc and cmdorc-frontend are configured.
    Use log_all=True to also configure cmdorc and textual-filelink loggers.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL or int)
        log_dir: Directory for log files (default: ~/.cmdorc/logs)
        log_filename: Log file name (default: cmdorc-tui.log)
        max_bytes: Maximum size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        format: Format preset ("simple" or "detailed")
        format_string: Custom format string (overrides format preset)
        log_all: Also configure cmdorc and textual-filelink loggers

    Returns:
        The textual_cmdorc logger (for convenience)

    Example:
        # Enable file logging for debugging
        setup_logging()

        # Enable with all packages for deep debugging
        setup_logging(log_all=True)
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)

    # Select format string
    if format_string is None:
        format_string = DETAILED_FORMAT if format == "detailed" else SIMPLE_FORMAT

    formatter = logging.Formatter(format_string)

    # Configure our namespaces (textual-cmdorc, cmdorc-frontend)
    our_namespaces = [TEXTUAL_CMDORC_NAMESPACE, CMDORC_FRONTEND_NAMESPACE]

    if log_all:
        # Let dependencies configure their own logging
        _setup_dependency_logging(level, log_dir, log_filename)

    # Create log directory if needed
    log_path = get_log_file_path(log_dir, log_filename)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create file handler with rotation
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    for namespace in our_namespaces:
        logger = logging.getLogger(namespace)
        logger.setLevel(level)
        logger.propagate = False  # Prevent duplicate logging to root

        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            if not isinstance(handler, logging.NullHandler):
                handler.close()
                logger.removeHandler(handler)

        # Add file handler
        logger.addHandler(file_handler)

    return logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)


def _setup_dependency_logging(
    level: int,
    log_dir: Path | str,
    log_filename: str,
) -> None:
    """Configure logging for cmdorc and textual-filelink packages.

    Calls their setup_logging functions if available.
    """
    # Try to use cmdorc's setup_logging
    try:
        from cmdorc import setup_logging as cmdorc_setup

        cmdorc_setup(
            level=level,
            console=False,  # TUI - no console output
            file=True,
            log_dir=log_dir,
            log_filename=log_filename.replace("cmdorc-tui", "cmdorc"),
        )
    except ImportError:
        pass  # cmdorc doesn't have logging module, use direct config above


def disable_logging() -> None:
    """Disable all logging for textual-cmdorc and related packages.

    Removes all handlers and restores NullHandler for silent operation.
    """
    namespaces = [
        TEXTUAL_CMDORC_NAMESPACE,
        CMDORC_FRONTEND_NAMESPACE,
        CMDORC_NAMESPACE,
        TEXTUAL_FILELINK_NAMESPACE,
    ]

    for namespace in namespaces:
        logger = logging.getLogger(namespace)
        logger.setLevel(logging.CRITICAL + 1)  # Effectively disable
        # Remove all handlers
        for handler in logger.handlers[:]:
            if not isinstance(handler, logging.NullHandler):
                handler.close()
                logger.removeHandler(handler)
        # Ensure NullHandler exists
        if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
            logger.addHandler(logging.NullHandler())

    # Try to call dependency disable functions
    try:
        from cmdorc import disable_logging as cmdorc_disable

        cmdorc_disable()
    except ImportError:
        pass

    try:
        from textual_filelink import disable_logging as filelink_disable

        filelink_disable()
    except ImportError:
        pass


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger for textual-cmdorc.

    Args:
        name: Optional child name (e.g., "widget" -> "textual_cmdorc.widget")

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"{TEXTUAL_CMDORC_NAMESPACE}.{name}")
    return logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)


# Install NullHandler by default (library best practice)
logging.getLogger(TEXTUAL_CMDORC_NAMESPACE).addHandler(logging.NullHandler())
logging.getLogger(CMDORC_FRONTEND_NAMESPACE).addHandler(logging.NullHandler())
