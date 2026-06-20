"""File mover — safe atomic moves with conflict resolution and undo log."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.shared.constants import ConflictStrategy

logger = get_logger(__name__)


class MoveError(Exception):
    """Raised when a file move operation fails."""


class MoveRecord:
    """A record of a file move operation for undo purposes."""

    __slots__ = ("destination", "rule_name", "source", "timestamp")

    def __init__(
        self,
        source: Path,
        destination: Path,
        rule_name: str,
        timestamp: datetime | None = None,
    ) -> None:
        self.source = source
        self.destination = destination
        self.rule_name = rule_name
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> dict:
        return {
            "source": str(self.source),
            "destination": str(self.destination),
            "rule_name": self.rule_name,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> MoveRecord:
        return cls(
            source=Path(data["source"]),
            destination=Path(data["destination"]),
            rule_name=data["rule_name"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class UndoLog:
    """Persistent undo log stored as JSON lines."""

    def __init__(self, log_path: Path) -> None:
        self._path = log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, move: MoveRecord) -> None:
        """Append a move record to the undo log."""
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(move.to_dict()) + "\n")

    def get_history(self, limit: int = 100) -> list[MoveRecord]:
        """Read the last N move records."""
        if not self._path.exists():
            return []

        records: list[MoveRecord] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(MoveRecord.from_dict(json.loads(line)))

        return records[-limit:]

    def undo_last(self) -> MoveRecord | None:
        """Undo the last move operation by moving the file back.

        Returns:
            The undone MoveRecord, or None if nothing to undo.
        """
        records = self.get_history(limit=1)
        if not records:
            return None

        record = records[-1]
        dest = record.destination
        source = record.source

        if not dest.exists():
            logger.warning("undo_file_missing", path=str(dest))
            return None

        # Move file back
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(source))
        logger.info("undo_move", source=str(dest), destination=str(source))

        # Remove the last line from the log
        self._remove_last_line()
        return record

    def _remove_last_line(self) -> None:
        """Remove the last line from the undo log file."""
        if not self._path.exists():
            return
        lines = self._path.read_text(encoding="utf-8").splitlines()
        if lines:
            self._path.write_text(
                "\n".join(lines[:-1]) + ("\n" if len(lines) > 1 else ""),
                encoding="utf-8",
            )


def resolve_conflict(destination: Path, strategy: str) -> Path | None:
    """Resolve a filename conflict at the destination.

    Args:
        destination: The intended destination path.
        strategy: One of "rename", "overwrite", "skip".

    Returns:
        The resolved destination path, or None if the file should be skipped.
    """
    if not destination.exists():
        return destination

    if strategy == "overwrite":
        return destination
    elif strategy == "skip":
        logger.info("file_skipped_conflict", path=str(destination))
        return None
    else:  # rename
        return _find_unique_name(destination)


def _find_unique_name(path: Path) -> Path:
    """Find a unique filename by appending (1), (2), etc."""
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_name = f"{stem} ({counter}){suffix}"
        candidate = parent / new_name
        if not candidate.exists():
            return candidate
        counter += 1
        if counter > 9999:
            raise MoveError(f"Cannot find unique name for {path} after 9999 attempts")


def move_file(
    source: Path,
    destination_dir: Path,
    conflict_strategy: ConflictStrategy | str = "rename",
    undo_log: UndoLog | None = None,
    rule_name: str = "unknown",
) -> Path | None:
    """Move a file to the destination directory safely.

    Args:
        source: Path to the source file.
        destination_dir: Target directory (will be created if needed).
        conflict_strategy: How to handle existing files at destination.
        undo_log: Optional undo log to record the move.
        rule_name: Name of the rule that triggered this move.

    Returns:
        The final destination path, or None if skipped.

    Raises:
        MoveError: If the move fails.
    """
    if not source.exists():
        raise MoveError(f"Source file does not exist: {source}")
    if not source.is_file():
        raise MoveError(f"Source is not a file: {source}")

    # Ensure destination directory exists
    destination_dir.mkdir(parents=True, exist_ok=True)

    # Full destination path (dir + filename)
    destination = destination_dir / source.name

    # Resolve conflicts
    resolved = resolve_conflict(destination, str(conflict_strategy))
    if resolved is None:
        return None  # Skipped

    try:
        shutil.move(str(source), str(resolved))
    except OSError as e:
        raise MoveError(f"Failed to move {source} → {resolved}: {e}") from e

    logger.info(
        "file_moved",
        source=str(source),
        destination=str(resolved),
        rule=rule_name,
    )

    # Record in undo log
    if undo_log is not None:
        record = MoveRecord(
            source=source,
            destination=resolved,
            rule_name=rule_name,
        )
        undo_log.record(record)

    return resolved
