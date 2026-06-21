"""AI engine — classifies files using Ollama local LLM as a fallback."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003 — used at runtime
from typing import TYPE_CHECKING

from src.core.analyzer.content_reader import get_file_context
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.shared.models import AISettings, Rule, RulesConfig

logger = get_logger(__name__)

CLASSIFICATION_PROMPT = (
    "You are a file organization assistant. "
    "Based on the file information below, suggest which category this file belongs to.\n\n"
    "Available categories (rules):\n"
    "{categories}\n\n"
    "File information:\n"
    "{file_context}\n\n"
    "Respond ONLY with a JSON object containing:\n"
    '- "rule_name": the exact name of the matching rule (or "unknown" if none fits)\n'
    '- "confidence": a number between 0.0 and 1.0\n\n'
    "Example response:\n"
    '{{"rule_name": "PDF Documents", "confidence": 0.85}}\n\n'
    "Your response (JSON only, no markdown):"
)


class AIClassificationResult:
    """Result of an AI classification attempt."""

    __slots__ = ("confidence", "rule_name")

    def __init__(self, rule_name: str, confidence: float) -> None:
        self.rule_name = rule_name
        self.confidence = confidence


class AIEngine:
    """Classifies files using Ollama local LLM.

    Args:
        settings: AI configuration (model, host, timeout).
        rules_config: Organization rules (used to build category list for prompt).
    """

    def __init__(self, settings: AISettings, rules_config: RulesConfig) -> None:
        self._settings = settings
        self._rules = rules_config
        self._consecutive_failures = 0
        self._max_failures_before_backoff = 3

    @property
    def is_available(self) -> bool:
        if not self._settings.enabled:
            return False
        # Re-enable after backoff period (every 10 calls after failure threshold)
        if self._consecutive_failures >= self._max_failures_before_backoff:
            return self._consecutive_failures % 10 == 0
        return True

    def classify_file(self, file_path: Path) -> AIClassificationResult | None:
        """Classify a file using Ollama.

        Args:
            file_path: Path to the file to classify.

        Returns:
            AIClassificationResult if successful, None otherwise.
        """
        if not self.is_available:
            self._consecutive_failures += 1
            return None

        # Check file size limit
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self._settings.max_file_size_mb:
                logger.debug("file_too_large_for_ai", file=file_path.name, size_mb=size_mb)
                return None
        except OSError:
            return None

        # Build context and prompt
        file_context = get_file_context(file_path)
        categories = self._build_categories_list()
        prompt = CLASSIFICATION_PROMPT.format(
            categories=categories,
            file_context=file_context,
        )

        # Call Ollama
        response_text = self._call_ollama(prompt)
        if response_text is None:
            return None

        # Success — reset failure counter
        self._consecutive_failures = 0

        # Parse response
        return self._parse_response(response_text)

    def get_matching_rule(self, file_path: Path) -> Rule | None:
        """Classify a file and return the matching Rule object.

        Args:
            file_path: Path to the file.

        Returns:
            The matched Rule, or None if classification fails or confidence is too low.
        """
        result = self.classify_file(file_path)
        if result is None:
            return None

        # Require minimum confidence
        if result.confidence < 0.6:
            logger.info(
                "ai_low_confidence",
                file=file_path.name,
                rule=result.rule_name,
                confidence=result.confidence,
            )
            return None

        # Find the rule by name
        for rule in self._rules.rules:
            if rule.name == result.rule_name and rule.enabled:
                logger.info(
                    "ai_classification_match",
                    file=file_path.name,
                    rule=result.rule_name,
                    confidence=result.confidence,
                )
                return rule

        logger.debug("ai_rule_not_found", rule_name=result.rule_name)
        return None

    def _build_categories_list(self) -> str:
        """Build a formatted list of available categories for the prompt."""
        lines = []
        for rule in self._rules.get_active_rules():
            exts = ", ".join(rule.condition.extensions) if rule.condition.extensions else "any"
            lines.append(f"- {rule.name} (extensions: {exts}, dest: {rule.destination})")
        return "\n".join(lines)

    def _call_ollama(self, prompt: str) -> str | None:
        """Make an HTTP request to the Ollama API.

        Returns:
            The response text, or None if the request fails.
        """
        try:
            import urllib.request

            url = f"{self._settings.host}/api/generate"
            payload = json.dumps({
                "model": self._settings.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 100,
                },
            }).encode("utf-8")

            req = urllib.request.Request(  # noqa: S310
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(  # noqa: S310
                req, timeout=self._settings.timeout_seconds
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")

        except Exception as e:
            self._consecutive_failures += 1
            logger.debug(
                "ollama_request_failed",
                error=str(e),
                failures=self._consecutive_failures,
            )
            return None

    def _parse_response(self, response_text: str) -> AIClassificationResult | None:
        """Parse the JSON response from Ollama."""
        try:
            # Clean up response (strip markdown fences if present)
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            data = json.loads(text)
            rule_name = data.get("rule_name", "unknown")
            confidence = float(data.get("confidence", 0.0))

            if rule_name == "unknown":
                return None

            return AIClassificationResult(
                rule_name=rule_name,
                confidence=min(max(confidence, 0.0), 1.0),  # Clamp to [0, 1]
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.debug("ai_response_parse_error", error=str(e), response=response_text[:200])
            return None
