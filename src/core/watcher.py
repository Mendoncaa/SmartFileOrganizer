"""File system watcher — monitors folders for new files using watchdog."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from watchdog.observers.api import BaseObserver

logger = get_logger(__name__)


class FileCallback(Protocol):
    """Protocol for the callback invoked when a new file is detected."""

    def __call__(self, path: Path) -> None: ...


class _NewFileHandler(FileSystemEventHandler):
    """Watchdog event handler that detects new files."""

    def __init__(self, callback: FileCallback) -> None:
        super().__init__()
        self._callback = callback

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.is_symlink():
            logger.debug("skipping_symlink", path=str(path))
            return
        logger.info("file_detected", path=str(path))
        self._callback(path)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        """Handle files moved INTO the watched folder (e.g., browser downloads)."""
        if event.is_directory:
            return
        path = Path(event.dest_path)
        if path.is_symlink():
            logger.debug("skipping_symlink", path=str(path))
            return
        logger.info("file_detected_via_move", path=str(path))
        self._callback(path)


class FolderWatcher:
    """Watches one or more folders for new files.

    Args:
        folders: List of (path, recursive) tuples to watch.
        callback: Function called with the Path of each new file detected.
    """

    def __init__(
        self,
        folders: list[tuple[Path, bool]],
        callback: FileCallback,
    ) -> None:
        self._folders = folders
        self._callback = callback
        self._observer: BaseObserver | None = None
        self._lock = threading.Lock()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start watching all configured folders."""
        with self._lock:
            if self._running:
                logger.warning("watcher_already_running")
                return

            self._observer = Observer()
            handler = _NewFileHandler(self._callback)

            for folder_path, recursive in self._folders:
                if not folder_path.exists():
                    logger.warning("watch_folder_not_found", path=str(folder_path))
                    continue
                self._observer.schedule(handler, str(folder_path), recursive=recursive)
                logger.info(
                    "watching_folder",
                    path=str(folder_path),
                    recursive=recursive,
                )

            self._observer.start()
            self._running = True
            logger.info("watcher_started", folder_count=len(self._folders))

    def stop(self) -> None:
        """Stop watching and clean up."""
        with self._lock:
            if not self._running or self._observer is None:
                return
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            self._running = False
            logger.info("watcher_stopped")
