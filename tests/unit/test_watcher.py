"""Unit tests for FolderWatcher and FileDebouncer."""

import time
from pathlib import Path
from unittest.mock import MagicMock

from src.core.debouncer import FileDebouncer
from src.core.watcher import FolderWatcher


class TestFolderWatcher:
    def test_start_and_stop(self, tmp_watch_dir: Path):
        callback = MagicMock()
        watcher = FolderWatcher(
            folders=[(tmp_watch_dir, False)],
            callback=callback,
        )
        assert not watcher.is_running
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_detects_new_file(self, tmp_watch_dir: Path):
        detected: list[Path] = []
        callback = lambda p: detected.append(p)  # noqa: E731

        watcher = FolderWatcher(
            folders=[(tmp_watch_dir, False)],
            callback=callback,
        )
        watcher.start()
        try:
            # Create a file in the watched folder
            test_file = tmp_watch_dir / "test.pdf"
            test_file.write_text("hello", encoding="utf-8")

            # Wait for event propagation
            time.sleep(1.0)
            assert len(detected) >= 1
            assert detected[0].name == "test.pdf"
        finally:
            watcher.stop()

    def test_ignores_directories(self, tmp_watch_dir: Path):
        detected: list[Path] = []
        callback = lambda p: detected.append(p)  # noqa: E731

        watcher = FolderWatcher(
            folders=[(tmp_watch_dir, False)],
            callback=callback,
        )
        watcher.start()
        try:
            # Create a subdirectory (should be ignored)
            subdir = tmp_watch_dir / "subdir"
            subdir.mkdir()
            time.sleep(0.5)
            assert len(detected) == 0
        finally:
            watcher.stop()

    def test_skips_nonexistent_folder(self, tmp_path: Path):
        callback = MagicMock()
        nonexistent = tmp_path / "does_not_exist"
        watcher = FolderWatcher(
            folders=[(nonexistent, False)],
            callback=callback,
        )
        # Should not raise, just log a warning
        watcher.start()
        watcher.stop()

    def test_start_is_idempotent(self, tmp_watch_dir: Path):
        callback = MagicMock()
        watcher = FolderWatcher(
            folders=[(tmp_watch_dir, False)],
            callback=callback,
        )
        watcher.start()
        watcher.start()  # Should not raise
        assert watcher.is_running
        watcher.stop()


class TestFileDebouncer:
    def test_calls_callback_after_stability(self, tmp_path: Path):
        processed: list[Path] = []
        callback = lambda p: processed.append(p)  # noqa: E731

        debouncer = FileDebouncer(callback=callback, delay=0.3)
        # Create a stable file
        test_file = tmp_path / "stable.pdf"
        test_file.write_text("content", encoding="utf-8")

        debouncer.file_detected(test_file)
        time.sleep(1.0)

        assert len(processed) == 1
        assert processed[0] == test_file
        debouncer.cancel_all()

    def test_resets_on_size_change(self, tmp_path: Path):
        processed: list[Path] = []
        callback = lambda p: processed.append(p)  # noqa: E731

        debouncer = FileDebouncer(callback=callback, delay=0.5)
        test_file = tmp_path / "growing.bin"
        test_file.write_bytes(b"a" * 100)

        debouncer.file_detected(test_file)
        # Simulate file still downloading (size changes)
        time.sleep(0.3)
        test_file.write_bytes(b"a" * 200)

        # After stability
        time.sleep(1.5)
        assert len(processed) == 1
        debouncer.cancel_all()

    def test_handles_deleted_file(self, tmp_path: Path):
        processed: list[Path] = []
        callback = lambda p: processed.append(p)  # noqa: E731

        debouncer = FileDebouncer(callback=callback, delay=0.3)
        test_file = tmp_path / "temp.txt"
        test_file.write_text("temp", encoding="utf-8")

        debouncer.file_detected(test_file)
        # Delete file before debounce completes
        test_file.unlink()
        time.sleep(1.0)

        # Should NOT call callback for deleted file
        assert len(processed) == 0
        debouncer.cancel_all()

    def test_cancel_all_stops_processing(self, tmp_path: Path):
        processed: list[Path] = []
        callback = lambda p: processed.append(p)  # noqa: E731

        debouncer = FileDebouncer(callback=callback, delay=0.5)
        test_file = tmp_path / "cancel_me.txt"
        test_file.write_text("data", encoding="utf-8")

        debouncer.file_detected(test_file)
        debouncer.cancel_all()
        time.sleep(1.0)

        assert len(processed) == 0

    def test_pending_count(self, tmp_path: Path):
        callback = MagicMock()
        debouncer = FileDebouncer(callback=callback, delay=2.0)

        file1 = tmp_path / "a.txt"
        file2 = tmp_path / "b.txt"
        file1.write_text("a", encoding="utf-8")
        file2.write_text("b", encoding="utf-8")

        debouncer.file_detected(file1)
        debouncer.file_detected(file2)
        assert debouncer.pending_count == 2

        debouncer.cancel_all()
        assert debouncer.pending_count == 0
