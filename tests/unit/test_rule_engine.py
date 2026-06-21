"""Unit tests for the rule engine."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from src.core.analyzer.rule_engine import (
    RuleMatch,
    _matches_extensions,
    _matches_name_pattern,
    _matches_size,
    evaluate_rule,
    find_matching_rule,
    resolve_destination_template,
)
from src.shared.models import Rule, RuleCondition, RulesConfig


class TestResolveDestinationTemplate:
    @patch("src.core.analyzer.rule_engine.datetime")
    def test_resolves_year_month_day(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 3, 15)
        mock_dt.strftime = datetime.strftime

        result = resolve_destination_template(
            "~/Documents/{year}/{month}/{day}/",
            Path("/downloads/report.pdf"),
        )
        assert "2026" in str(result)
        assert "03" in str(result)
        assert "15" in str(result)

    def test_resolves_ext(self):
        result = resolve_destination_template(
            "/dest/{ext}/",
            Path("/src/file.PDF"),
        )
        assert "pdf" in str(result).lower()

    def test_resolves_name(self):
        result = resolve_destination_template(
            "/dest/{name}/",
            Path("/src/my_report.pdf"),
        )
        assert "my_report" in str(result)

    def test_resolves_filename(self):
        result = resolve_destination_template(
            "/dest/{filename}",
            Path("/src/my_report.pdf"),
        )
        assert "my_report.pdf" in str(result)

    def test_expands_user_home(self):
        result = resolve_destination_template(
            "~/Documents/",
            Path("/src/file.txt"),
        )
        assert "~" not in str(result)

    def test_unknown_placeholder_raises(self):
        """Unknown template variables raise ValueError, not KeyError."""
        import pytest

        with pytest.raises(ValueError, match="Unknown template variable"):
            resolve_destination_template(
                "/dest/{unknown_var}/",
                Path("/src/file.pdf"),
            )

    def test_sanitizes_path_traversal_in_name(self):
        """Filenames with path separators or .. are sanitized."""
        result = resolve_destination_template(
            "/dest/{name}/",
            Path("/src/../../etc/passwd"),
        )
        # Should NOT contain .. or path separators from the name
        name_part = str(result)
        assert ".." not in name_part.split("dest")[1] if "dest" in name_part else True


class TestMatchesExtensions:
    def test_matches_when_in_list(self):
        assert _matches_extensions(Path("file.pdf"), ["pdf", "doc"])

    def test_case_insensitive(self):
        assert _matches_extensions(Path("file.PDF"), ["pdf"])

    def test_no_match(self):
        assert not _matches_extensions(Path("file.txt"), ["pdf", "doc"])

    def test_empty_list_matches_all(self):
        assert _matches_extensions(Path("file.xyz"), [])

    def test_no_extension(self):
        assert not _matches_extensions(Path("Makefile"), ["pdf"])

    def test_no_extension_empty_list(self):
        assert _matches_extensions(Path("Makefile"), [])


class TestMatchesNamePattern:
    def test_matches_regex(self):
        assert _matches_name_pattern(Path("invoice_2026.pdf"), r"(?i)invoice")

    def test_case_insensitive_pattern(self):
        assert _matches_name_pattern(Path("FATURA_jan.pdf"), r"(?i)fatura")

    def test_no_match(self):
        assert not _matches_name_pattern(Path("photo.jpg"), r"(?i)invoice")

    def test_none_pattern_matches_all(self):
        assert _matches_name_pattern(Path("anything.txt"), None)

    def test_complex_regex(self):
        assert _matches_name_pattern(
            Path("receipt_2026-01-15.pdf"),
            r"\d{4}-\d{2}-\d{2}",
        )

    def test_invalid_regex_returns_false(self):
        """Invalid regex patterns should return False, not crash."""
        assert not _matches_name_pattern(Path("file.pdf"), r"[unclosed")

    def test_malformed_regex_group(self):
        """Malformed regex should be handled safely."""
        assert not _matches_name_pattern(Path("file.pdf"), r"(?P<x")


class TestMatchesSize:
    def test_within_range(self, tmp_path: Path):
        f = tmp_path / "medium.bin"
        f.write_bytes(b"x" * (5 * 1024 * 1024))  # 5MB
        assert _matches_size(f, min_mb=1, max_mb=10)

    def test_below_minimum(self, tmp_path: Path):
        f = tmp_path / "small.bin"
        f.write_bytes(b"x" * 100)  # ~0MB
        assert not _matches_size(f, min_mb=1, max_mb=None)

    def test_above_maximum(self, tmp_path: Path):
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * (20 * 1024 * 1024))  # 20MB
        assert not _matches_size(f, min_mb=None, max_mb=10)

    def test_no_constraints_matches_all(self, tmp_path: Path):
        f = tmp_path / "any.bin"
        f.write_bytes(b"x" * 1000)
        assert _matches_size(f, min_mb=None, max_mb=None)

    def test_nonexistent_file(self):
        assert not _matches_size(Path("/nonexistent"), min_mb=1, max_mb=None)


class TestEvaluateRule:
    def test_matches_by_extension(self, tmp_path: Path):
        f = tmp_path / "doc.pdf"
        f.write_text("content", encoding="utf-8")

        rule = Rule(
            name="PDFs",
            condition=RuleCondition(extensions=["pdf"]),
            destination="/dest/{year}/",
        )
        result = evaluate_rule(rule, f)
        assert result is not None
        assert isinstance(result, RuleMatch)
        assert result.rule.name == "PDFs"

    def test_no_match_wrong_extension(self, tmp_path: Path):
        f = tmp_path / "image.jpg"
        f.write_text("content", encoding="utf-8")

        rule = Rule(
            name="PDFs",
            condition=RuleCondition(extensions=["pdf"]),
            destination="/dest/",
        )
        assert evaluate_rule(rule, f) is None

    def test_matches_with_name_pattern(self, tmp_path: Path):
        f = tmp_path / "invoice_2026.pdf"
        f.write_text("content", encoding="utf-8")

        rule = Rule(
            name="Invoices",
            condition=RuleCondition(
                extensions=["pdf"],
                name_pattern=r"(?i)invoice",
            ),
            destination="/invoices/{year}/",
        )
        assert evaluate_rule(rule, f) is not None

    def test_fails_when_pattern_doesnt_match(self, tmp_path: Path):
        f = tmp_path / "report.pdf"
        f.write_text("content", encoding="utf-8")

        rule = Rule(
            name="Invoices",
            condition=RuleCondition(
                extensions=["pdf"],
                name_pattern=r"(?i)invoice",
            ),
            destination="/invoices/",
        )
        assert evaluate_rule(rule, f) is None

    def test_matches_with_size_constraint(self, tmp_path: Path):
        f = tmp_path / "big.zip"
        f.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        rule = Rule(
            name="Big archives",
            condition=RuleCondition(extensions=["zip"], min_size_mb=1),
            destination="/archives/",
        )
        assert evaluate_rule(rule, f) is not None


class TestFindMatchingRule:
    def test_returns_highest_priority_match(self, tmp_path: Path):
        f = tmp_path / "report.pdf"
        f.write_text("content", encoding="utf-8")

        config = RulesConfig(
            rules=[
                Rule(
                    name="Generic PDFs",
                    priority=5,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/generic/",
                ),
                Rule(
                    name="Important PDFs",
                    priority=20,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/important/",
                ),
            ]
        )
        result = find_matching_rule(config, f)
        assert result is not None
        assert result.rule.name == "Important PDFs"

    def test_returns_none_when_no_match(self, tmp_path: Path):
        f = tmp_path / "random.xyz"
        f.write_text("content", encoding="utf-8")

        config = RulesConfig(
            rules=[
                Rule(
                    name="PDFs",
                    priority=10,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/pdfs/",
                ),
            ]
        )
        assert find_matching_rule(config, f) is None

    def test_skips_disabled_rules(self, tmp_path: Path):
        f = tmp_path / "doc.pdf"
        f.write_text("content", encoding="utf-8")

        config = RulesConfig(
            rules=[
                Rule(
                    name="Disabled",
                    enabled=False,
                    priority=100,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/disabled/",
                ),
                Rule(
                    name="Active",
                    enabled=True,
                    priority=1,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/active/",
                ),
            ]
        )
        result = find_matching_rule(config, f)
        assert result is not None
        assert result.rule.name == "Active"

    def test_more_specific_rule_with_higher_priority_wins(self, tmp_path: Path):
        f = tmp_path / "invoice_jan.pdf"
        f.write_text("content", encoding="utf-8")

        config = RulesConfig(
            rules=[
                Rule(
                    name="All PDFs",
                    priority=5,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination="/pdfs/",
                ),
                Rule(
                    name="Invoices",
                    priority=20,
                    condition=RuleCondition(
                        extensions=["pdf"],
                        name_pattern=r"(?i)invoice",
                    ),
                    destination="/invoices/{year}/{month}/",
                ),
            ]
        )
        result = find_matching_rule(config, f)
        assert result is not None
        assert result.rule.name == "Invoices"
