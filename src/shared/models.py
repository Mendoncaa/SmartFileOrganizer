"""Shared Pydantic models — Rule, FileEvent, Config, Settings."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.shared.constants import ConflictStrategy, EventType, FileAction

# ──────────────────────────────────────────────
# Rule Models
# ──────────────────────────────────────────────


class RuleCondition(BaseModel):
    """Conditions that must ALL match for a rule to trigger."""

    extensions: list[str] = Field(default_factory=list, description="File extensions (without dot)")
    name_pattern: str | None = Field(
        default=None,
        max_length=200,
        description="Regex pattern to match against filename (capped to limit ReDoS risk)",
    )
    min_size_mb: float | None = Field(default=None, ge=0, description="Minimum file size in MB")
    max_size_mb: float | None = Field(default=None, ge=0, description="Maximum file size in MB")

    @field_validator("extensions", mode="before")
    @classmethod
    def normalize_extensions(cls, v: list[str]) -> list[str]:
        """Strip leading dots and lowercase all extensions."""
        return [ext.lstrip(".").lower() for ext in v]


class Rule(BaseModel):
    """A single organization rule: condition → destination."""

    name: str = Field(description="Human-readable rule name")
    enabled: bool = Field(default=True)
    priority: int = Field(default=0, description="Higher priority rules are evaluated first")
    condition: RuleCondition
    destination: str = Field(
        description="Destination path template (supports {year}, {month}, {ext})"
    )
    action: FileAction = Field(default=FileAction.MOVE)
    conflict_strategy: ConflictStrategy = Field(default=ConflictStrategy.RENAME)


# ──────────────────────────────────────────────
# Event Models
# ──────────────────────────────────────────────


class FileEvent(BaseModel):
    """Represents a file system event detected by the watcher."""

    event_type: EventType
    source_path: Path
    destination_path: Path | None = None
    rule_name: str | None = Field(default=None, description="Rule that matched, if any")
    timestamp: datetime = Field(default_factory=datetime.now)
    error_message: str | None = None


# ──────────────────────────────────────────────
# Configuration Models
# ──────────────────────────────────────────────


class WatchFolder(BaseModel):
    """A folder to be monitored."""

    path: Path
    recursive: bool = Field(default=False, description="Watch subdirectories too")
    enabled: bool = Field(default=True)

    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand ~ and environment variables in path."""
        return Path(v).expanduser()


class AISettings(BaseModel):
    """Configuration for the Ollama AI fallback."""

    enabled: bool = Field(default=True)
    model: str = Field(default="phi3:mini", description="Ollama model to use")
    host: str = Field(default="http://localhost:11434")
    timeout_seconds: int = Field(default=30, ge=5)
    max_file_size_mb: float = Field(default=50.0, ge=1)


class LoggingSettings(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_dir: Path = Field(default=Path("logs"))
    max_file_size_mb: float = Field(default=10.0, ge=1)
    backup_count: int = Field(default=5, ge=1)


class Settings(BaseModel):
    """Global application settings (settings.yaml)."""

    watch_folders: list[WatchFolder] = Field(default_factory=list, min_length=1)
    debounce_seconds: float = Field(default=2.0, ge=0.5, le=30.0)
    conflict_strategy: ConflictStrategy = Field(default=ConflictStrategy.RENAME)
    ai: AISettings = Field(default_factory=AISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


class RulesConfig(BaseModel):
    """Container for all organization rules (rules.yaml)."""

    rules: list[Rule] = Field(default_factory=list)

    def get_active_rules(self) -> list[Rule]:
        """Return enabled rules sorted by priority (highest first)."""
        return sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True,
        )
