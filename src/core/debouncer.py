"""Debounce mechanism — waits for file stability before processing."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path  # noqa: TC003 — used at runtime
from typing import Protocol

from src.shared.logging import get_logger

logger = get_logger(__name__)


class StableFileCallback(Protocol):
    """Protocol for the callback invoked when a file is stable (download complete)."""

    def __call__(self, path: Path) -> None: ...


class FileDebouncer:
    """Debounces file events: waits until a file's size stops changing.

    When a file is detected, we wait `delay` seconds and then check if the file
    size has changed. If it has, we reset the timer. If it hasn't (stable), we
    invoke the callback.

    Args:
        callback: Function to call when the file is stable.
        delay: Seconds to wait before checking stability.
        max_retries: Maximum number of stability checks before giving up.
        max_workers: Maximum concurrent file processing threads.
    """

    def __init__(
        self,
        callback: StableFileCallback,
        delay: float = 2.0,
        max_retries: int = 15,
        max_workers: int = 4,
    ) -> None:
        self._callback = callback
        self._delay = delay
        self._max_retries = max_retries
        self._pending: dict[Path, threading.Timer] = {}
        self._sizes: dict[Path, int] = {}
        self._retries: dict[Path, int] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="sfo-worker"
        )

    def file_detected(self, path: Path) -> None:
        """Called when a new file is detected. Starts the debounce timer."""
        with self._lock:
            # Cancel any existing timer for this file
            if path in self._pending:
                self._pending[path].cancel()

            self._sizes[path] = self._get_size(path)
            self._retries[path] = 0
            self._schedule_check(path)

    def _schedule_check(self, path: Path) -> None:
        """Schedule a stability check after the delay period."""
        timer = threading.Timer(self._delay, self._check_stability, args=[path])
        timer.daemon = True
        self._pending[path] = timer
        timer.start()

    def _check_stability(self, path: Path) -> None:
        """Check if file size has stabilized."""
        with self._lock:
            if path not in self._sizes:
                return

            # File was deleted during debounce
            if not path.exists():
                logger.debug("file_disappeared_during_debounce", path=str(path))
                self._cleanup(path)
                return

            current_size = self._get_size(path)
            previous_size = self._sizes[path]
            retries = self._retries.get(path, 0)

            if current_size == previous_size and current_size > 0:
                # File is stable — invoke callback
                logger.info(
                    "file_stable",
                    path=str(path),
                    size_bytes=current_size,
                    checks=retries + 1,
                )
                self._cleanup(path)
                # Submit to thread pool (back-pressure via max_workers)
                self._executor.submit(self._safe_callback, path)
            elif retries >= self._max_retries:
                # Give up after too many retries
                logger.warning(
                    "file_debounce_timeout",
                    path=str(path),
                    retries=retries,
                )
                self._cleanup(path)
            else:
                # File still changing — reset timer
                logger.debug(
                    "file_still_changing",
                    path=str(path),
                    previous_size=previous_size,
                    current_size=current_size,
                    retry=retries + 1,
                )
                self._sizes[path] = current_size
                self._retries[path] = retries + 1
                self._schedule_check(path)

    def _get_size(self, path: Path) -> int:
        """Get file size safely, returning 0 if file doesn't exist."""
        try:
            return path.stat().st_size
        except OSError:
            return 0

    def _cleanup(self, path: Path) -> None:
        """Remove tracking data for a file."""
        self._pending.pop(path, None)
        self._sizes.pop(path, None)
        self._retries.pop(path, None)

    def _safe_callback(self, path: Path) -> None:
        """Invoke callback with error handling (runs in thread pool)."""
        if not path.exists():
            logger.debug("file_disappeared_before_processing", path=str(path))
            return
        try:
            self._callback(path)
        except Exception:
            logger.exception("callback_error", path=str(path))

    def cancel_all(self) -> None:
        """Cancel all pending debounce timers and shutdown thread pool."""
        with self._lock:
            for timer in self._pending.values():
                timer.cancel()
            self._pending.clear()
            self._sizes.clear()
            self._retries.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)

    @property
    def pending_count(self) -> int:
        """Number of files currently being debounced."""
        with self._lock:
            return len(self._pending)
