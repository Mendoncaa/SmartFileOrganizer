"""Dispatcher — orchestrates the file organization pipeline.

Pipeline: file detected → rule matching → (AI fallback) → move file → emit event.
"""

from __future__ import annotations

import threading
from pathlib import Path  # noqa: TC003 — used at runtime
from typing import TYPE_CHECKING

from src.core.analyzer.ai_engine import AIEngine
from src.core.analyzer.rule_engine import find_matching_rule, resolve_destination_template
from src.core.mover import MoveError, UndoLog, move_file
from src.shared.constants import EventType
from src.shared.logging import get_logger
from src.shared.models import FileEvent

if TYPE_CHECKING:
    from src.shared.models import RulesConfig, Settings


logger = get_logger(__name__)


class Dispatcher:
    """Orchestrates the full file organization pipeline.

    Args:
        rules_config: Loaded organization rules.
        settings: Application settings.
        undo_log: Undo log for recording moves.
    """

    def __init__(
        self,
        rules_config: RulesConfig,
        settings: Settings,
        undo_log: UndoLog | None = None,
    ) -> None:
        self._rules = rules_config
        self._settings = settings
        self._undo_log = undo_log
        self._event_listeners: list[callable] = []
        self._ai_engine: AIEngine | None = None
        self._lock = threading.Lock()

        # Initialize AI engine if enabled
        if settings.ai.enabled:
            self._ai_engine = AIEngine(settings.ai, rules_config)

    def add_event_listener(self, listener: callable) -> None:
        """Register a listener to receive FileEvent notifications."""
        self._event_listeners.append(listener)

    def _emit_event(self, event: FileEvent) -> None:
        """Notify all registered listeners of an event."""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("event_listener_error")

    def process_file(self, file_path: Path) -> FileEvent:
        """Process a single file through the organization pipeline.

        Steps:
            1. Verify file still exists
            2. Match against rules (highest priority first)
            3. If no rule match: try AI classification (fallback)
            4. If match: move file to resolved destination
            5. If still no match: skip

        Args:
            file_path: Path to the newly detected file.

        Returns:
            FileEvent describing what happened.
        """
        logger.info("processing_file", file=str(file_path))

        # Step 1: Verify file exists and is not a symlink
        if not file_path.exists():
            event = FileEvent(
                event_type=EventType.ERROR,
                source_path=file_path,
                error_message="File no longer exists",
            )
            self._emit_event(event)
            return event

        if file_path.is_symlink():
            event = FileEvent(
                event_type=EventType.FILE_SKIPPED,
                source_path=file_path,
                error_message="Symlinks are skipped for safety",
            )
            self._emit_event(event)
            return event

        # Step 2: Match against rules (thread-safe). A malformed destination
        # template raises ValueError — surface it as an ERROR event instead of
        # silently dying in the worker thread.
        try:
            with self._lock:
                match = find_matching_rule(self._rules, file_path)

            if match is None:
                # Step 3: Try AI fallback
                ai_rule = self._try_ai_classification(file_path)
                if ai_rule is not None:
                    destination = resolve_destination_template(ai_rule.destination, file_path)
                    # Create a synthetic match for the move step
                    from src.core.analyzer.rule_engine import RuleMatch

                    match = RuleMatch(rule=ai_rule, resolved_destination=destination)
                    logger.info("ai_fallback_matched", file=file_path.name, rule=ai_rule.name)
        except ValueError as e:
            event = FileEvent(
                event_type=EventType.ERROR,
                source_path=file_path,
                error_message=f"Invalid destination template: {e}",
            )
            logger.error("template_resolution_failed", file=file_path.name, error=str(e))
            self._emit_event(event)
            return event

        if match is None:
            # No rule and no AI match — skip
            event = FileEvent(
                event_type=EventType.FILE_SKIPPED,
                source_path=file_path,
            )
            logger.info("file_skipped_no_rule", file=file_path.name)
            self._emit_event(event)
            return event

        # Step 3: Move file
        try:
            destination = move_file(
                source=file_path,
                destination_dir=match.resolved_destination,
                conflict_strategy=match.rule.conflict_strategy,
                undo_log=self._undo_log,
                rule_name=match.rule.name,
            )
        except MoveError as e:
            event = FileEvent(
                event_type=EventType.ERROR,
                source_path=file_path,
                error_message=str(e),
                rule_name=match.rule.name,
            )
            logger.error("move_failed", file=file_path.name, error=str(e))
            self._emit_event(event)
            return event

        if destination is None:
            # Skipped due to conflict strategy
            event = FileEvent(
                event_type=EventType.FILE_SKIPPED,
                source_path=file_path,
                rule_name=match.rule.name,
            )
            self._emit_event(event)
            return event

        # Step 4: Success
        event = FileEvent(
            event_type=EventType.FILE_MOVED,
            source_path=file_path,
            destination_path=destination,
            rule_name=match.rule.name,
        )
        logger.info(
            "file_organized",
            file=file_path.name,
            rule=match.rule.name,
            destination=str(destination),
        )
        self._emit_event(event)
        return event

    def _try_ai_classification(self, file_path: Path) -> object | None:
        """Attempt to classify a file using the AI engine.

        Returns:
            A Rule object if AI classification succeeds, None otherwise.
        """
        if self._ai_engine is None or not self._ai_engine.is_available:
            return None

        logger.debug("trying_ai_classification", file=file_path.name)
        return self._ai_engine.get_matching_rule(file_path)
