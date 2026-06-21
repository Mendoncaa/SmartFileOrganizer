"""Unit tests for the file mover and undo log."""

from pathlib import Path

import pytest

from src.core.mover import (
    MoveError,
    MoveRecord,
    UndoLog,
    _find_unique_name,
    move_file,
    resolve_conflict,
)


class TestResolveConflict:
    def test_no_conflict(self, tmp_path: Path):
        dest = tmp_path / "file.pdf"
        result = resolve_conflict(dest, "rename")
        assert result == dest

    def test_rename_strategy(self, tmp_path: Path):
        existing = tmp_path / "file.pdf"
        existing.write_text("existing", encoding="utf-8")

        result = resolve_conflict(existing, "rename")
        assert result == tmp_path / "file (1).pdf"

    def test_overwrite_strategy(self, tmp_path: Path):
        existing = tmp_path / "file.pdf"
        existing.write_text("existing", encoding="utf-8")

        result = resolve_conflict(existing, "overwrite")
        assert result == existing

    def test_skip_strategy(self, tmp_path: Path):
        existing = tmp_path / "file.pdf"
        existing.write_text("existing", encoding="utf-8")

        result = resolve_conflict(existing, "skip")
        assert result is None


class TestFindUniqueName:
    def test_first_conflict(self, tmp_path: Path):
        (tmp_path / "file.pdf").write_text("a", encoding="utf-8")
        result = _find_unique_name(tmp_path / "file.pdf")
        assert result == tmp_path / "file (1).pdf"

    def test_multiple_conflicts(self, tmp_path: Path):
        (tmp_path / "file.pdf").write_text("a", encoding="utf-8")
        (tmp_path / "file (1).pdf").write_text("b", encoding="utf-8")
        (tmp_path / "file (2).pdf").write_text("c", encoding="utf-8")
        result = _find_unique_name(tmp_path / "file.pdf")
        assert result == tmp_path / "file (3).pdf"


class TestMoveFile:
    def test_basic_move(self, tmp_path: Path):
        src = tmp_path / "source" / "doc.pdf"
        src.parent.mkdir()
        src.write_text("content", encoding="utf-8")
        dest_dir = tmp_path / "destination"

        result = move_file(src, dest_dir)
        assert result == dest_dir / "doc.pdf"
        assert result.exists()
        assert not src.exists()

    def test_creates_destination_dir(self, tmp_path: Path):
        src = tmp_path / "doc.pdf"
        src.write_text("content", encoding="utf-8")
        dest_dir = tmp_path / "deep" / "nested" / "dir"

        result = move_file(src, dest_dir)
        assert result is not None
        assert result.exists()
        assert dest_dir.exists()

    def test_rename_on_conflict(self, tmp_path: Path):
        src = tmp_path / "src" / "file.pdf"
        src.parent.mkdir()
        src.write_text("new content", encoding="utf-8")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "file.pdf").write_text("old content", encoding="utf-8")

        result = move_file(src, dest_dir, conflict_strategy="rename")
        assert result == dest_dir / "file (1).pdf"
        assert result.read_text(encoding="utf-8") == "new content"
        assert (dest_dir / "file.pdf").read_text(encoding="utf-8") == "old content"

    def test_overwrite_on_conflict(self, tmp_path: Path):
        src = tmp_path / "src" / "file.pdf"
        src.parent.mkdir()
        src.write_text("new content", encoding="utf-8")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "file.pdf").write_text("old content", encoding="utf-8")

        result = move_file(src, dest_dir, conflict_strategy="overwrite")
        assert result == dest_dir / "file.pdf"
        assert result.read_text(encoding="utf-8") == "new content"

    def test_skip_on_conflict(self, tmp_path: Path):
        src = tmp_path / "src" / "file.pdf"
        src.parent.mkdir()
        src.write_text("new content", encoding="utf-8")

        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "file.pdf").write_text("old content", encoding="utf-8")

        result = move_file(src, dest_dir, conflict_strategy="skip")
        assert result is None
        assert src.exists()  # Source not moved

    def test_nonexistent_source_raises(self, tmp_path: Path):
        with pytest.raises(MoveError, match="does not exist"):
            move_file(tmp_path / "ghost.pdf", tmp_path / "dest")

    def test_directory_source_raises(self, tmp_path: Path):
        src = tmp_path / "a_dir"
        src.mkdir()
        with pytest.raises(MoveError, match="not a file"):
            move_file(src, tmp_path / "dest")

    def test_symlink_source_raises(self, tmp_path: Path):
        target = tmp_path / "real.pdf"
        target.write_text("content", encoding="utf-8")
        link = tmp_path / "link.pdf"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Symlinks require elevated privileges on this OS")
        with pytest.raises(MoveError, match="symlink"):
            move_file(link, tmp_path / "dest")

    def test_destination_is_file_raises(self, tmp_path: Path):
        src = tmp_path / "file.pdf"
        src.write_text("content", encoding="utf-8")
        dest_as_file = tmp_path / "not_a_dir"
        dest_as_file.write_text("I'm a file", encoding="utf-8")
        with pytest.raises(MoveError, match="not a directory"):
            move_file(src, dest_as_file)

    def test_records_in_undo_log(self, tmp_path: Path):
        src = tmp_path / "file.pdf"
        src.write_text("content", encoding="utf-8")
        dest_dir = tmp_path / "dest"
        log = UndoLog(tmp_path / "undo.jsonl")

        move_file(src, dest_dir, undo_log=log, rule_name="TestRule")

        history = log.get_history()
        assert len(history) == 1
        assert history[0].rule_name == "TestRule"
        assert history[0].source == src


class TestUndoLog:
    def test_record_and_retrieve(self, tmp_path: Path):
        log = UndoLog(tmp_path / "undo.jsonl")
        record = MoveRecord(
            source=Path("/src/file.pdf"),
            destination=Path("/dest/file.pdf"),
            rule_name="PDFs",
        )
        log.record(record)

        history = log.get_history()
        assert len(history) == 1
        assert history[0].source == Path("/src/file.pdf")
        assert history[0].rule_name == "PDFs"

    def test_multiple_records(self, tmp_path: Path):
        log = UndoLog(tmp_path / "undo.jsonl")
        for i in range(5):
            log.record(
                MoveRecord(
                    source=Path(f"/src/file{i}.pdf"),
                    destination=Path(f"/dest/file{i}.pdf"),
                    rule_name=f"Rule{i}",
                )
            )

        history = log.get_history(limit=3)
        assert len(history) == 3

    def test_empty_log(self, tmp_path: Path):
        log = UndoLog(tmp_path / "undo.jsonl")
        assert log.get_history() == []

    def test_log_is_trimmed_when_too_large(self, tmp_path: Path):
        from src.core.mover import MAX_UNDO_RECORDS, UNDO_TRIM_THRESHOLD

        log_path = tmp_path / "undo.jsonl"
        log = UndoLog(log_path)
        for i in range(UNDO_TRIM_THRESHOLD + 5):
            log.record(
                MoveRecord(
                    source=Path(f"/src/file{i}.pdf"),
                    destination=Path(f"/dest/file{i}.pdf"),
                    rule_name="Rule",
                )
            )

        # After trimming, the log stays bounded (never grows unbounded) and was
        # trimmed down towards MAX_UNDO_RECORDS rather than keeping all records.
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert MAX_UNDO_RECORDS <= len(lines) <= UNDO_TRIM_THRESHOLD
        # The most recent record must be preserved after trimming.
        history = log.get_history(limit=1)
        last_index = UNDO_TRIM_THRESHOLD + 4
        assert history[0].source == Path(f"/src/file{last_index}.pdf")

    def test_undo_last_moves_file_back(self, tmp_path: Path):
        # Setup: file already moved
        original_dir = tmp_path / "original"
        original_dir.mkdir()
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        src_file = original_dir / "doc.pdf"
        dest_file = dest_dir / "doc.pdf"
        dest_file.write_text("content", encoding="utf-8")

        log = UndoLog(tmp_path / "undo.jsonl")
        log.record(MoveRecord(source=src_file, destination=dest_file, rule_name="Test"))

        # Undo
        result = log.undo_last()
        assert result is not None
        assert src_file.exists()
        assert not dest_file.exists()

    def test_undo_empty_log(self, tmp_path: Path):
        log = UndoLog(tmp_path / "undo.jsonl")
        assert log.undo_last() is None


class TestMoveRecord:
    def test_serialization_roundtrip(self):
        record = MoveRecord(
            source=Path("/a/b.pdf"),
            destination=Path("/c/d.pdf"),
            rule_name="MyRule",
        )
        data = record.to_dict()
        restored = MoveRecord.from_dict(data)
        assert restored.source == record.source
        assert restored.destination == record.destination
        assert restored.rule_name == record.rule_name
