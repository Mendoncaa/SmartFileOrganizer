"""Structured logging setup using structlog with file rotation."""

import sys
from logging import FileHandler, StreamHandler, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog

from src.shared.models import LoggingSettings

_configured = False


def setup_logging(settings: LoggingSettings | None = None) -> None:
    """Configure structlog with console + rotating file output.

    Args:
        settings: Logging configuration. Uses defaults if None.
    """
    global _configured
    if _configured:
        return

    if settings is None:
        settings = LoggingSettings()

    # Ensure log directory exists
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "smart-file-organizer.log"

    # Standard library logging handlers
    handlers: list[StreamHandler] = [
        StreamHandler(sys.stdout),
        RotatingFileHandler(
            filename=str(log_file),
            maxBytes=int(settings.max_file_size_mb * 1024 * 1024),
            backupCount=settings.backup_count,
            encoding="utf-8",
        ),
    ]

    # Configure standard library root logger
    root_logger = getLogger()
    root_logger.setLevel(settings.level)
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
            if sys.stdout.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        A bound structlog logger.
    """
    if not _configured:
        setup_logging()
    return structlog.get_logger(name)


def reset_logging() -> None:
    """Reset logging configuration (for testing)."""
    global _configured
    _configured = False
    structlog.reset_defaults()
    root = getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        if isinstance(handler, FileHandler):
            handler.close()
