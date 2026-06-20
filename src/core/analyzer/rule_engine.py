"""Rule engine — matches files against organization rules."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.shared.models import Rule, RulesConfig

logger = get_logger(__name__)


class RuleMatch:
    """Result of a successful rule match."""

    __slots__ = ("resolved_destination", "rule")

    def __init__(self, rule: Rule, resolved_destination: Path) -> None:
        self.rule = rule
        self.resolved_destination = resolved_destination

    def __repr__(self) -> str:
        return f"RuleMatch(rule={self.rule.name!r}, dest={self.resolved_destination})"


def resolve_destination_template(template: str, file_path: Path) -> Path:
    """Resolve a destination template with dynamic variables.

    Supported variables:
        {year}  — current year (4 digits)
        {month} — current month (2 digits, zero-padded)
        {day}   — current day (2 digits, zero-padded)
        {ext}   — file extension without dot (e.g., "pdf")
        {name}  — filename without extension
        {filename} — full filename with extension

    Args:
        template: Destination path template string.
        file_path: The source file path.

    Returns:
        Resolved absolute Path.
    """
    now = datetime.now()
    ext = file_path.suffix.lstrip(".").lower()

    variables = {
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "ext": ext,
        "name": file_path.stem,
        "filename": file_path.name,
    }

    resolved = template.format(**variables)
    return Path(resolved).expanduser()


def _matches_extensions(file_path: Path, extensions: list[str]) -> bool:
    """Check if the file extension matches any in the list."""
    if not extensions:
        return True  # No extension filter = matches all
    file_ext = file_path.suffix.lstrip(".").lower()
    return file_ext in extensions


def _matches_name_pattern(file_path: Path, pattern: str | None) -> bool:
    """Check if the filename matches the regex pattern."""
    if pattern is None:
        return True  # No pattern = matches all
    return bool(re.search(pattern, file_path.name))


def _matches_size(file_path: Path, min_mb: float | None, max_mb: float | None) -> bool:
    """Check if the file size is within the specified range."""
    if min_mb is None and max_mb is None:
        return True  # No size filter

    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
    except OSError:
        return False

    if min_mb is not None and size_mb < min_mb:
        return False
    return not (max_mb is not None and size_mb > max_mb)


def evaluate_rule(rule: Rule, file_path: Path) -> RuleMatch | None:
    """Evaluate a single rule against a file.

    Returns:
        RuleMatch if all conditions match, None otherwise.
    """
    cond = rule.condition

    if not _matches_extensions(file_path, cond.extensions):
        return None
    if not _matches_name_pattern(file_path, cond.name_pattern):
        return None
    if not _matches_size(file_path, cond.min_size_mb, cond.max_size_mb):
        return None

    # All conditions match — resolve destination
    destination = resolve_destination_template(rule.destination, file_path)
    return RuleMatch(rule=rule, resolved_destination=destination)


def find_matching_rule(rules_config: RulesConfig, file_path: Path) -> RuleMatch | None:
    """Find the first matching rule for a file (sorted by priority).

    Args:
        rules_config: The loaded rules configuration.
        file_path: Path to the file to evaluate.

    Returns:
        RuleMatch for the highest-priority matching rule, or None if no match.
    """
    for rule in rules_config.get_active_rules():
        match = evaluate_rule(rule, file_path)
        if match is not None:
            logger.info(
                "rule_matched",
                file=file_path.name,
                rule=rule.name,
                destination=str(match.resolved_destination),
            )
            return match

    logger.debug("no_rule_matched", file=file_path.name)
    return None
