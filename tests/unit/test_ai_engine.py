"""Unit tests for content_reader and ai_engine with mocked Ollama."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.analyzer.ai_engine import AIEngine
from src.core.analyzer.content_reader import (
    extract_file_metadata,
    get_file_context,
)
from src.core.dispatcher import Dispatcher
from src.shared.constants import EventType
from src.shared.models import (
    AISettings,
    Rule,
    RuleCondition,
    RulesConfig,
    Settings,
    WatchFolder,
)


class TestContentReader:
    def test_extract_metadata(self, tmp_path: Path):
        f = tmp_path / "invoice_2026.pdf"
        f.write_bytes(b"\x00" * (1024 * 1024))  # 1MB

        meta = extract_file_metadata(f)
        assert meta["filename"] == "invoice_2026.pdf"
        assert meta["extension"] == "pdf"
        assert meta["stem"] == "invoice_2026"
        assert float(meta["size_mb"]) == pytest.approx(1.0, abs=0.01)

    def test_extract_metadata_no_extension(self, tmp_path: Path):
        f = tmp_path / "Makefile"
        f.write_text("all:", encoding="utf-8")

        meta = extract_file_metadata(f)
        assert meta["extension"] == ""
        assert meta["stem"] == "Makefile"

    def test_get_file_context_text_file(self, tmp_path: Path):
        f = tmp_path / "notes.txt"
        f.write_text("Meeting notes from January", encoding="utf-8")

        context = get_file_context(f)
        assert "notes.txt" in context
        assert "txt" in context
        assert "Meeting notes from January" in context

    def test_get_file_context_binary_file(self, tmp_path: Path):
        f = tmp_path / "photo.jpg"
        f.write_bytes(b"\xff\xd8\xff" + b"\x00" * 1000)

        context = get_file_context(f)
        assert "photo.jpg" in context
        assert "jpg" in context
        # No content preview for binary
        assert "Content preview" not in context


class TestAIEngine:
    def _make_settings(self) -> AISettings:
        return AISettings(
            enabled=True,
            model="phi3:mini",
            host="http://localhost:11434",
            timeout_seconds=10,
        )

    def _make_rules(self) -> RulesConfig:
        return RulesConfig(
            rules=[
                Rule(
                    name="PDFs",
                    priority=10,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/docs/pdfs/{year}/",
                ),
                Rule(
                    name="Images",
                    priority=5,
                    condition=RuleCondition(extensions=["jpg", "png"]),
                    destination="/pics/",
                ),
                Rule(
                    name="Invoices",
                    priority=20,
                    condition=RuleCondition(
                        extensions=["pdf"],
                        name_pattern=r"(?i)invoice",
                    ),
                    destination="/invoices/{year}/",
                ),
            ]
        )

    def test_classify_returns_result_on_success(self, tmp_path: Path):
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "mystery_doc.pdf"
        f.write_text("Some content", encoding="utf-8")

        mock_response = json.dumps({"rule_name": "PDFs", "confidence": 0.9})

        with patch.object(engine, "_call_ollama", return_value=mock_response):
            result = engine.classify_file(f)

        assert result is not None
        assert result.rule_name == "PDFs"
        assert result.confidence == 0.9

    def test_classify_returns_none_when_disabled(self, tmp_path: Path):
        settings = AISettings(enabled=False)
        engine = AIEngine(settings, self._make_rules())
        f = tmp_path / "file.txt"
        f.write_text("content", encoding="utf-8")

        result = engine.classify_file(f)
        assert result is None

    def test_classify_returns_none_on_unknown(self, tmp_path: Path):
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "file.xyz"
        f.write_text("content", encoding="utf-8")

        mock_response = json.dumps({"rule_name": "unknown", "confidence": 0.3})

        with patch.object(engine, "_call_ollama", return_value=mock_response):
            result = engine.classify_file(f)

        assert result is None

    def test_classify_returns_none_on_invalid_json(self, tmp_path: Path):
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "file.txt"
        f.write_text("content", encoding="utf-8")

        with patch.object(engine, "_call_ollama", return_value="not json at all"):
            result = engine.classify_file(f)

        assert result is None

    def test_get_matching_rule_returns_rule(self, tmp_path: Path):
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "report.pdf"
        f.write_text("annual report", encoding="utf-8")

        mock_response = json.dumps({"rule_name": "Invoices", "confidence": 0.85})

        with patch.object(engine, "_call_ollama", return_value=mock_response):
            rule = engine.get_matching_rule(f)

        assert rule is not None
        assert rule.name == "Invoices"

    def test_get_matching_rule_low_confidence(self, tmp_path: Path):
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "ambiguous.pdf"
        f.write_text("ambiguous", encoding="utf-8")

        mock_response = json.dumps({"rule_name": "PDFs", "confidence": 0.4})

        with patch.object(engine, "_call_ollama", return_value=mock_response):
            rule = engine.get_matching_rule(f)

        assert rule is None  # Below 0.6 threshold

    def test_file_too_large_skipped(self, tmp_path: Path):
        settings = AISettings(enabled=True, max_file_size_mb=1.0)  # 1MB limit
        engine = AIEngine(settings, self._make_rules())
        f = tmp_path / "large.bin"
        f.write_bytes(b"\x00" * (2 * 1024 * 1024))  # 2MB > 1MB limit

        result = engine.classify_file(f)
        assert result is None

    def test_handles_markdown_wrapped_json(self, tmp_path: Path):
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "doc.pdf"
        f.write_text("content", encoding="utf-8")

        # Some models wrap JSON in markdown code fences
        mock_response = '```json\n{"rule_name": "PDFs", "confidence": 0.8}\n```'

        with patch.object(engine, "_call_ollama", return_value=mock_response):
            result = engine.classify_file(f)

        assert result is not None
        assert result.rule_name == "PDFs"

    def test_recovers_after_ollama_comes_back(self, tmp_path: Path):
        """AI engine should retry periodically after failures, not stay dead."""
        engine = AIEngine(self._make_settings(), self._make_rules())
        f = tmp_path / "doc.pdf"
        f.write_text("content", encoding="utf-8")

        # Below threshold — still available
        engine._consecutive_failures = 2
        assert engine.is_available

        # At threshold but NOT a retry multiple — backed off
        engine._consecutive_failures = 5
        assert not engine.is_available  # 5 >= 3 and 5 % 10 != 0

        # At a retry multiple (every 10th failure) — available again for one try
        engine._consecutive_failures = 10
        assert engine.is_available  # 10 % 10 == 0 → retry

        # Non-retry failure count
        engine._consecutive_failures = 13
        assert not engine.is_available  # 13 % 10 != 0

        # Simulate recovery — Ollama responds at retry point
        engine._consecutive_failures = 20  # retry window (20 % 10 == 0)
        mock_response = json.dumps({"rule_name": "PDFs", "confidence": 0.9})
        with patch.object(engine, "_call_ollama", return_value=mock_response):
            result = engine.classify_file(f)

        assert result is not None
        assert result.rule_name == "PDFs"
        assert engine._consecutive_failures == 0  # Reset on success
        assert engine.is_available  # Fully recovered


class TestDispatcherWithAI:
    """Test the dispatcher with AI fallback integration."""

    def test_ai_fallback_when_no_rule_matches(self, tmp_path: Path):
        """A file with no matching rule gets classified by AI."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        dest_dir = tmp_path / "organized"

        settings = Settings(
            watch_folders=[WatchFolder(path=watch_dir)],
            ai=AISettings(enabled=True),
        )
        rules = RulesConfig(
            rules=[
                Rule(
                    name="Documents",
                    priority=10,
                    condition=RuleCondition(extensions=["doc"]),
                    destination=str(dest_dir / "docs"),
                ),
            ]
        )

        dispatcher = Dispatcher(rules, settings)

        # Mock AI to classify the file
        mock_response = json.dumps({"rule_name": "Documents", "confidence": 0.9})
        with patch.object(dispatcher._ai_engine, "_call_ollama", return_value=mock_response):
            # Create a file that doesn't match any rule by extension
            mystery = watch_dir / "meeting_notes.txt"
            mystery.write_text("Important meeting notes", encoding="utf-8")

            event = dispatcher.process_file(mystery)

        assert event.event_type == EventType.FILE_MOVED
        assert event.rule_name == "Documents"

    def test_ai_disabled_skips_unmatched(self, tmp_path: Path):
        """When AI is disabled, unmatched files are simply skipped."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()

        settings = Settings(
            watch_folders=[WatchFolder(path=watch_dir)],
            ai=AISettings(enabled=False),
        )
        rules = RulesConfig(
            rules=[
                Rule(
                    name="PDFs",
                    priority=10,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/pdfs/",
                ),
            ]
        )

        dispatcher = Dispatcher(rules, settings)
        mystery = watch_dir / "unknown.xyz"
        mystery.write_text("content", encoding="utf-8")

        event = dispatcher.process_file(mystery)
        assert event.event_type == EventType.FILE_SKIPPED
        assert mystery.exists()  # Not moved
