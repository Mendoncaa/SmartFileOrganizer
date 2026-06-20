"""Shared constants — paths, ports, enums."""

from enum import StrEnum
from pathlib import Path

# Default config paths (relative to project root or user home)
DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_RULES_FILE = DEFAULT_CONFIG_DIR / "rules.yaml"
DEFAULT_SETTINGS_FILE = DEFAULT_CONFIG_DIR / "settings.yaml"

# IPC
IPC_DEFAULT_PORT = 5577
IPC_PUB_PORT = 5578

# Watcher
DEBOUNCE_SECONDS = 2.0
MAX_FILE_SIZE_FOR_AI_MB = 50


class FileAction(StrEnum):
    """Actions that can be performed on a file."""

    MOVE = "move"
    COPY = "copy"
    SKIP = "skip"


class ConflictStrategy(StrEnum):
    """How to handle filename conflicts at destination."""

    RENAME = "rename"  # Append (1), (2), etc.
    OVERWRITE = "overwrite"
    SKIP = "skip"


class ServiceCommand(StrEnum):
    """Commands that can be sent to the core service via IPC."""

    PAUSE = "pause"
    RESUME = "resume"
    RELOAD_CONFIG = "reload_config"
    STATUS = "status"
    SHUTDOWN = "shutdown"


class EventType(StrEnum):
    """Types of events published by the core service."""

    FILE_DETECTED = "file_detected"
    FILE_MOVED = "file_moved"
    FILE_SKIPPED = "file_skipped"
    ERROR = "error"
    SERVICE_STATUS = "service_status"
