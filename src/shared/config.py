"""Configuration loader — reads and validates YAML config files."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from src.shared.constants import DEFAULT_RULES_FILE, DEFAULT_SETTINGS_FILE
from src.shared.models import RulesConfig, Settings


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""


def _resolve_config_path(path: Path | str | None, default: Path, base_dir: Path) -> Path:
    """Resolve a config path relative to a base directory."""
    if path is None:
        resolved = base_dir / default
    else:
        resolved = Path(path)
        if not resolved.is_absolute():
            resolved = base_dir / resolved
    return resolved


def load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    if not path.is_file():
        raise ConfigError(f"Configuration path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def load_settings(
    path: Path | str | None = None,
    base_dir: Path | None = None,
) -> Settings:
    """Load and validate settings from a YAML file.

    Args:
        path: Explicit path to settings.yaml. If None, uses default location.
        base_dir: Base directory for resolving relative paths. Defaults to CWD.

    Returns:
        Validated Settings model.

    Raises:
        ConfigError: If file is missing, malformed, or fails validation.
    """
    if base_dir is None:
        base_dir = Path.cwd()

    resolved = _resolve_config_path(path, DEFAULT_SETTINGS_FILE, base_dir)
    data = load_yaml(resolved)

    try:
        return Settings(**data)
    except ValidationError as e:
        raise ConfigError(f"Invalid settings in {resolved}:\n{e}") from e


def load_rules(
    path: Path | str | None = None,
    base_dir: Path | None = None,
) -> RulesConfig:
    """Load and validate organization rules from a YAML file.

    Args:
        path: Explicit path to rules.yaml. If None, uses default location.
        base_dir: Base directory for resolving relative paths. Defaults to CWD.

    Returns:
        Validated RulesConfig model.

    Raises:
        ConfigError: If file is missing, malformed, or fails validation.
    """
    if base_dir is None:
        base_dir = Path.cwd()

    resolved = _resolve_config_path(path, DEFAULT_RULES_FILE, base_dir)
    data = load_yaml(resolved)

    try:
        return RulesConfig(**data)
    except ValidationError as e:
        raise ConfigError(f"Invalid rules in {resolved}:\n{e}") from e
