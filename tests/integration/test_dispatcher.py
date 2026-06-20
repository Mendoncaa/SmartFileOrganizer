"""Integration test — end-to-end file organization pipeline."""

import time
from pathlib import Path

from src.core.debouncer import FileDebouncer
from src.core.dispatcher import Dispatcher
from src.core.mover import UndoLog
from src.core.watcher import FolderWatcher
from src.shared.constants import EventType
from src.shared.models import (
    FileEvent,
    Rule,
    RuleCondition,
    RulesConfig,
    Settings,
    WatchFolder,
)


class TestEndToEndPipeline:
    """Full integration: watcher → debouncer → dispatcher → mover."""

    def _make_settings(self, watch_dir: Path) -> Settings:
        return Settings(
            watch_folders=[WatchFolder(path=watch_dir)],
            debounce_seconds=0.5,
        )

    def _make_rules(self, dest_dir: Path) -> RulesConfig:
        return RulesConfig(
            rules=[
                Rule(
                    name="PDFs",
                    priority=10,
                    condition=RuleCondition(extensions=["pdf"]),
                    destination=str(dest_dir / "pdfs" / "{year}"),
                ),
                Rule(
                    name="Images",
                    priority=5,
                    condition=RuleCondition(extensions=["jpg", "png"]),
                    destination=str(dest_dir / "images"),
                ),
                Rule(
                    name="Invoices",
                    priority=20,
                    condition=RuleCondition(
                        extensions=["pdf"],
                        name_pattern=r"(?i)(invoice|fatura)",
                    ),
                    destination=str(dest_dir / "invoices" / "{year}"),
                ),
            ]
        )

    def test_pdf_moved_to_correct_folder(self, tmp_path: Path):
        """A PDF dropped in watch folder ends up in pdfs/{year}/."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        dest_dir = tmp_path / "organized"

        settings = self._make_settings(watch_dir)
        rules = self._make_rules(dest_dir)
        undo_log = UndoLog(tmp_path / "undo.jsonl")

        dispatcher = Dispatcher(rules, settings, undo_log)
        events: list[FileEvent] = []
        dispatcher.add_event_listener(events.append)

        # Create PDF
        pdf = watch_dir / "report.pdf"
        pdf.write_text("PDF content", encoding="utf-8")

        # Process directly (simulating post-debounce callback)
        dispatcher.process_file(pdf)

        # Verify
        assert len(events) == 1
        assert events[0].event_type == EventType.FILE_MOVED
        assert events[0].rule_name == "PDFs"
        assert not pdf.exists()  # Moved away
        # Check destination exists
        moved_files = list((dest_dir / "pdfs").rglob("report.pdf"))
        assert len(moved_files) == 1

    def test_invoice_gets_higher_priority(self, tmp_path: Path):
        """An invoice PDF matches the more specific Invoices rule (priority 20 > 10)."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        dest_dir = tmp_path / "organized"

        settings = self._make_settings(watch_dir)
        rules = self._make_rules(dest_dir)
        dispatcher = Dispatcher(rules, settings)

        invoice = watch_dir / "invoice_january.pdf"
        invoice.write_text("Invoice content", encoding="utf-8")

        event = dispatcher.process_file(invoice)
        assert event.event_type == EventType.FILE_MOVED
        assert event.rule_name == "Invoices"

    def test_unmatched_file_is_skipped(self, tmp_path: Path):
        """A .xyz file with no matching rule is skipped."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        dest_dir = tmp_path / "organized"

        settings = self._make_settings(watch_dir)
        rules = self._make_rules(dest_dir)
        dispatcher = Dispatcher(rules, settings)

        unknown = watch_dir / "random.xyz"
        unknown.write_text("unknown", encoding="utf-8")

        event = dispatcher.process_file(unknown)
        assert event.event_type == EventType.FILE_SKIPPED
        assert unknown.exists()  # Not moved

    def test_full_watcher_to_mover_pipeline(self, tmp_path: Path):
        """Full E2E: file created → watcher → debouncer → dispatcher → moved."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        dest_dir = tmp_path / "organized"

        settings = self._make_settings(watch_dir)
        rules = self._make_rules(dest_dir)
        dispatcher = Dispatcher(rules, settings)
        events: list[FileEvent] = []
        dispatcher.add_event_listener(events.append)

        # Wire up: watcher → debouncer → dispatcher
        debouncer = FileDebouncer(
            callback=dispatcher.process_file,
            delay=0.3,
        )
        watcher = FolderWatcher(
            folders=[(watch_dir, False)],
            callback=debouncer.file_detected,
        )

        watcher.start()
        try:
            # Drop a file
            img = watch_dir / "photo.jpg"
            img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 1000)

            # Wait for watcher + debounce + processing
            time.sleep(2.0)

            assert len(events) >= 1
            assert events[0].event_type == EventType.FILE_MOVED
            assert events[0].rule_name == "Images"
            assert not img.exists()
            assert (dest_dir / "images" / "photo.jpg").exists()
        finally:
            watcher.stop()
            debouncer.cancel_all()

    def test_undo_reverses_last_move(self, tmp_path: Path):
        """Undo log correctly reverses the last file move."""
        watch_dir = tmp_path / "downloads"
        watch_dir.mkdir()
        dest_dir = tmp_path / "organized"

        settings = self._make_settings(watch_dir)
        rules = self._make_rules(dest_dir)
        undo_log = UndoLog(tmp_path / "undo.jsonl")
        dispatcher = Dispatcher(rules, settings, undo_log)

        # Move a file
        pdf = watch_dir / "contract.pdf"
        pdf.write_text("contract", encoding="utf-8")
        dispatcher.process_file(pdf)
        assert not pdf.exists()

        # Undo
        record = undo_log.undo_last()
        assert record is not None
        assert pdf.exists()
        assert pdf.read_text(encoding="utf-8") == "contract"
