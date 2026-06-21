"""Unit tests for shared Pydantic models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.shared.constants import ConflictStrategy, EventType, FileAction
from src.shared.models import (
    AISettings,
    FileEvent,
    Rule,
    RuleCondition,
    RulesConfig,
    Settings,
    WatchFolder,
)


class TestRuleCondition:
    def test_normalize_extensions_strips_dots(self):
        cond = RuleCondition(extensions=[".pdf", ".PDF", "txt", ".Docx"])
        assert cond.extensions == ["pdf", "pdf", "txt", "docx"]

    def test_empty_extensions_is_valid(self):
        cond = RuleCondition()
        assert cond.extensions == []

    def test_size_constraints(self):
        cond = RuleCondition(min_size_mb=0, max_size_mb=100)
        assert cond.min_size_mb == 0
        assert cond.max_size_mb == 100

    def test_negative_size_rejected(self):
        with pytest.raises(ValidationError):
            RuleCondition(min_size_mb=-1)

    def test_name_pattern_length_capped(self):
        # Overly long patterns are rejected to limit ReDoS risk.
        with pytest.raises(ValidationError):
            RuleCondition(name_pattern="a" * 201)
        # A reasonable pattern is accepted.
        cond = RuleCondition(name_pattern="(?i)(invoice|fatura)")
        assert cond.name_pattern == "(?i)(invoice|fatura)"


class TestRule:
    def test_full_rule_creation(self):
        rule = Rule(
            name="PDFs to Documents",
            condition=RuleCondition(extensions=["pdf"]),
            destination="~/Documents/PDFs/{year}/",
            priority=10,
        )
        assert rule.name == "PDFs to Documents"
        assert rule.enabled is True
        assert rule.action == FileAction.MOVE
        assert rule.conflict_strategy == ConflictStrategy.RENAME
        assert rule.priority == 10

    def test_rule_defaults(self):
        rule = Rule(
            name="Test",
            condition=RuleCondition(),
            destination="/tmp/test",
        )
        assert rule.enabled is True
        assert rule.priority == 0


class TestRulesConfig:
    def test_get_active_rules_filters_disabled(self):
        config = RulesConfig(
            rules=[
                Rule(
                    name="Active",
                    enabled=True,
                    priority=5,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/tmp",
                ),
                Rule(
                    name="Disabled",
                    enabled=False,
                    priority=10,
                    condition=RuleCondition(extensions=["txt"]),
                    destination="/tmp",
                ),
            ]
        )
        active = config.get_active_rules()
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_get_active_rules_sorted_by_priority(self):
        config = RulesConfig(
            rules=[
                Rule(
                    name="Low",
                    priority=1,
                    condition=RuleCondition(),
                    destination="/tmp",
                ),
                Rule(
                    name="High",
                    priority=100,
                    condition=RuleCondition(),
                    destination="/tmp",
                ),
                Rule(
                    name="Mid",
                    priority=50,
                    condition=RuleCondition(),
                    destination="/tmp",
                ),
            ]
        )
        active = config.get_active_rules()
        assert [r.name for r in active] == ["High", "Mid", "Low"]


class TestFileEvent:
    def test_event_creation(self):
        event = FileEvent(
            event_type=EventType.FILE_MOVED,
            source_path=Path("/downloads/file.pdf"),
            destination_path=Path("/documents/file.pdf"),
            rule_name="PDFs",
        )
        assert event.event_type == EventType.FILE_MOVED
        assert event.timestamp is not None

    def test_error_event(self):
        event = FileEvent(
            event_type=EventType.ERROR,
            source_path=Path("/downloads/file.pdf"),
            error_message="Permission denied",
        )
        assert event.error_message == "Permission denied"
        assert event.destination_path is None


class TestWatchFolder:
    def test_expand_user_path(self):
        folder = WatchFolder(path="~/Downloads")
        assert "~" not in str(folder.path)

    def test_defaults(self):
        folder = WatchFolder(path="/tmp/watch")
        assert folder.recursive is False
        assert folder.enabled is True


class TestSettings:
    def test_valid_settings(self):
        settings = Settings(
            watch_folders=[WatchFolder(path="/tmp/watch")],
            debounce_seconds=3.0,
        )
        assert settings.debounce_seconds == 3.0
        assert settings.ai.enabled is True
        assert settings.logging.level == "INFO"

    def test_empty_watch_folders_rejected(self):
        with pytest.raises(ValidationError):
            Settings(watch_folders=[])

    def test_debounce_out_of_range_rejected(self):
        with pytest.raises(ValidationError):
            Settings(
                watch_folders=[WatchFolder(path="/tmp")],
                debounce_seconds=0.1,  # below min 0.5
            )


class TestAISettings:
    def test_defaults(self):
        ai = AISettings()
        assert ai.model == "phi3:mini"
        assert ai.host == "http://localhost:11434"
        assert ai.timeout_seconds == 30

    def test_timeout_minimum(self):
        with pytest.raises(ValidationError):
            AISettings(timeout_seconds=2)  # below min 5
