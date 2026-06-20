"""Unit tests for structured logging setup."""

from pathlib import Path

from src.shared.logging import get_logger, reset_logging, setup_logging
from src.shared.models import LoggingSettings


class TestLogging:
    def setup_method(self):
        """Reset logging before each test."""
        reset_logging()

    def teardown_method(self):
        """Reset logging after each test."""
        reset_logging()

    def test_setup_creates_log_directory(self, tmp_path: Path):
        log_dir = tmp_path / "test_logs"
        settings = LoggingSettings(level="DEBUG", log_dir=log_dir)
        setup_logging(settings)
        assert log_dir.exists()

    def test_setup_creates_log_file(self, tmp_path: Path):
        log_dir = tmp_path / "test_logs"
        settings = LoggingSettings(level="DEBUG", log_dir=log_dir)
        setup_logging(settings)
        logger = get_logger("test")
        logger.info("test message", key="value")
        log_file = log_dir / "smart-file-organizer.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content

    def test_get_logger_returns_bound_logger(self, tmp_path: Path):
        settings = LoggingSettings(log_dir=tmp_path / "logs")
        setup_logging(settings)
        logger = get_logger("my.module")
        assert logger is not None

    def test_setup_is_idempotent(self, tmp_path: Path):
        settings = LoggingSettings(log_dir=tmp_path / "logs")
        setup_logging(settings)
        setup_logging(settings)  # Should not raise or double-add handlers

    def test_structured_fields_in_log(self, tmp_path: Path):
        log_dir = tmp_path / "logs"
        settings = LoggingSettings(level="DEBUG", log_dir=log_dir)
        setup_logging(settings)
        logger = get_logger("test")
        logger.info("file moved", source="/a/b.pdf", destination="/c/d.pdf")
        log_file = log_dir / "smart-file-organizer.log"
        content = log_file.read_text(encoding="utf-8")
        assert "file moved" in content
