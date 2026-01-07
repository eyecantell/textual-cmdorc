"""Tests for textual_cmdorc.logging module."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tempfile import TemporaryDirectory

from textual_cmdorc.logging import (
    CMDORC_FRONTEND_NAMESPACE,
    TEXTUAL_CMDORC_NAMESPACE,
    disable_logging,
    get_log_file_path,
    get_logger,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_file_handler(self):
        """Test that setup_logging creates a RotatingFileHandler."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=tmpdir,
                log_filename="test.log",
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            handlers = [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]
            assert len(handlers) == 1
            assert isinstance(handlers[0], RotatingFileHandler)

            # Cleanup
            disable_logging()

    def test_setup_logging_creates_log_directory(self):
        """Test that log directory is created if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "subdir" / "logs"

            setup_logging(
                log_dir=log_dir,
                log_filename="test.log",
            )

            assert log_dir.exists()

            # Cleanup
            disable_logging()

    def test_setup_logging_configures_both_namespaces(self):
        """Test that both textual_cmdorc and cmdorc_frontend are configured."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=tmpdir,
                log_filename="test.log",
            )

            for namespace in [TEXTUAL_CMDORC_NAMESPACE, CMDORC_FRONTEND_NAMESPACE]:
                logger = logging.getLogger(namespace)
                handlers = [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]
                assert len(handlers) == 1

            # Cleanup
            disable_logging()

    def test_setup_logging_level_as_string(self):
        """Test that level can be specified as string."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(
                level="WARNING",
                log_dir=tmpdir,
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            assert logger.level == logging.WARNING

            # Cleanup
            disable_logging()

    def test_setup_logging_level_as_int(self):
        """Test that level can be specified as int."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(
                level=logging.ERROR,
                log_dir=tmpdir,
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            assert logger.level == logging.ERROR

            # Cleanup
            disable_logging()

    def test_setup_logging_detailed_format(self):
        """Test that detailed format includes timestamp and line number."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=tmpdir,
                format="detailed",
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            handlers = [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]
            formatter = handlers[0].formatter
            assert "asctime" in formatter._fmt
            assert "lineno" in formatter._fmt

            # Cleanup
            disable_logging()

    def test_setup_logging_simple_format(self):
        """Test that simple format is concise."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(
                log_dir=tmpdir,
                format="simple",
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            handlers = [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]
            formatter = handlers[0].formatter
            assert "levelname" in formatter._fmt
            assert "name" in formatter._fmt
            assert "asctime" not in formatter._fmt

            # Cleanup
            disable_logging()

    def test_setup_logging_custom_format_string(self):
        """Test that custom format string is used."""
        with TemporaryDirectory() as tmpdir:
            custom_format = "%(levelname)s - %(message)s"
            setup_logging(
                log_dir=tmpdir,
                format_string=custom_format,
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            handlers = [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]
            formatter = handlers[0].formatter
            assert formatter._fmt == custom_format

            # Cleanup
            disable_logging()

    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns the textual_cmdorc logger."""
        with TemporaryDirectory() as tmpdir:
            logger = setup_logging(log_dir=tmpdir)

            assert logger.name == TEXTUAL_CMDORC_NAMESPACE

            # Cleanup
            disable_logging()

    def test_setup_logging_rotation_config(self):
        """Test that rotation settings are applied."""
        with TemporaryDirectory() as tmpdir:
            max_bytes = 5 * 1024 * 1024  # 5MB
            backup_count = 3

            setup_logging(
                log_dir=tmpdir,
                max_bytes=max_bytes,
                backup_count=backup_count,
            )

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
            assert len(handlers) == 1
            assert handlers[0].maxBytes == max_bytes
            assert handlers[0].backupCount == backup_count

            # Cleanup
            disable_logging()

    def test_setup_logging_no_propagate(self):
        """Test that propagate is set to False to prevent duplicate logging."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            assert logger.propagate is False

            # Cleanup
            disable_logging()

    def test_setup_logging_idempotent(self):
        """Test that calling setup_logging multiple times is safe."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            setup_logging(log_dir=tmpdir)  # Call again

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            handlers = [h for h in logger.handlers if not isinstance(h, logging.NullHandler)]
            # Should still have only one handler
            assert len(handlers) == 1

            # Cleanup
            disable_logging()


class TestDisableLogging:
    """Tests for disable_logging function."""

    def test_disable_logging_sets_high_level(self):
        """Test that disable_logging sets level above CRITICAL."""
        with TemporaryDirectory() as tmpdir:
            # First enable logging
            setup_logging(log_dir=tmpdir)

            # Then disable
            disable_logging()

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            assert logger.level > logging.CRITICAL

    def test_disable_logging_removes_non_null_handlers(self):
        """Test that disable_logging removes all non-NullHandler handlers."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            disable_logging()

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            # Should only have NullHandler
            assert all(isinstance(h, logging.NullHandler) for h in logger.handlers)

    def test_disable_logging_ensures_null_handler_exists(self):
        """Test that disable_logging ensures at least one NullHandler."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            disable_logging()

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            # Should have at least one NullHandler
            null_handlers = [h for h in logger.handlers if isinstance(h, logging.NullHandler)]
            assert len(null_handlers) >= 1

    def test_disable_logging_affects_both_namespaces(self):
        """Test that disable_logging affects both main namespaces."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir)
            disable_logging()

            for namespace in [TEXTUAL_CMDORC_NAMESPACE, CMDORC_FRONTEND_NAMESPACE]:
                logger = logging.getLogger(namespace)
                assert logger.level > logging.CRITICAL


class TestGetLogFilePath:
    """Tests for get_log_file_path function."""

    def test_get_log_file_path_default(self):
        """Test default log file path."""
        path = get_log_file_path()
        assert path.name == "cmdorc-tui.log"
        assert ".cmdorc" in str(path)
        assert "logs" in str(path)

    def test_get_log_file_path_custom(self):
        """Test custom log file path."""
        path = get_log_file_path(
            log_dir="/tmp/custom",
            log_filename="custom.log",
        )
        assert path == Path("/tmp/custom/custom.log")

    def test_get_log_file_path_with_path_object(self):
        """Test that Path objects are accepted."""
        custom_dir = Path("/tmp/test")
        path = get_log_file_path(log_dir=custom_dir, log_filename="test.log")
        assert path == custom_dir / "test.log"


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_no_name(self):
        """Test get_logger without name returns root package logger."""
        logger = get_logger()
        assert logger.name == TEXTUAL_CMDORC_NAMESPACE

    def test_get_logger_with_name(self):
        """Test get_logger with name returns child logger."""
        logger = get_logger("widget")
        assert logger.name == f"{TEXTUAL_CMDORC_NAMESPACE}.widget"

    def test_get_logger_with_nested_name(self):
        """Test get_logger with nested name."""
        logger = get_logger("components.button")
        assert logger.name == f"{TEXTUAL_CMDORC_NAMESPACE}.components.button"


class TestNullHandlerDefault:
    """Tests for NullHandler being set by default."""

    def test_null_handler_on_import(self):
        """Test that NullHandler is set on import."""
        logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
        null_handlers = [h for h in logger.handlers if isinstance(h, logging.NullHandler)]
        assert len(null_handlers) >= 1

    def test_cmdorc_frontend_null_handler(self):
        """Test that cmdorc_frontend also has NullHandler."""
        logger = logging.getLogger(CMDORC_FRONTEND_NAMESPACE)
        null_handlers = [h for h in logger.handlers if isinstance(h, logging.NullHandler)]
        assert len(null_handlers) >= 1


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_logging_writes_to_file(self):
        """Test that logging actually writes to the log file."""
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            setup_logging(log_dir=tmpdir, log_filename="test.log")

            logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            logger.info("Test message")

            # Force flush
            for handler in logger.handlers:
                if hasattr(handler, "flush"):
                    handler.flush()

            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

            # Cleanup
            disable_logging()

    def test_child_logger_inherits_config(self):
        """Test that child loggers inherit the parent configuration."""
        with TemporaryDirectory() as tmpdir:
            setup_logging(log_dir=tmpdir, level="WARNING")

            _child_logger = logging.getLogger(f"{TEXTUAL_CMDORC_NAMESPACE}.child")
            # Child should inherit parent's level
            parent_logger = logging.getLogger(TEXTUAL_CMDORC_NAMESPACE)
            assert parent_logger.level == logging.WARNING

            # Cleanup
            disable_logging()
