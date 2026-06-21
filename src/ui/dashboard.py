"""Dashboard — real-time log viewer and statistics panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.ui.ipc_client import IPCClient

logger = get_logger(__name__)

# Maximum rows in the event table to prevent memory leak
_MAX_TABLE_ROWS = 500


class DashboardWindow(QMainWindow):
    """Main dashboard window showing real-time file organization events.

    Uses a pyqtSignal to safely marshal events from the IPC background
    thread to the Qt GUI thread (Qt requires all widget ops on GUI thread).
    """

    _event_received = pyqtSignal(dict)

    def __init__(self, ipc_client: IPCClient) -> None:
        super().__init__()
        self._client = ipc_client
        self._event_count = 0
        self._moved_count = 0
        self._skipped_count = 0
        self._error_count = 0

        self._setup_ui()
        # Connect signal→slot (queued connection auto-marshals to GUI thread)
        self._event_received.connect(self._on_event)
        # IPC callback emits the signal (safe from any thread)
        self._client.on_event(self._event_received.emit)

    def _setup_ui(self) -> None:
        """Build the dashboard UI."""
        self.setWindowTitle("Smart File Organizer — Dashboard")
        self.setMinimumSize(800, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Stats bar
        stats_layout = QHBoxLayout()
        self._lbl_moved = QLabel("Moved: 0")
        self._lbl_skipped = QLabel("Skipped: 0")
        self._lbl_errors = QLabel("Errors: 0")
        self._lbl_total = QLabel("Total: 0")

        for lbl in (self._lbl_total, self._lbl_moved, self._lbl_skipped, self._lbl_errors):
            lbl.setStyleSheet("font-weight: bold; padding: 4px 12px;")
            stats_layout.addWidget(lbl)

        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Events table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["Time", "Event", "File", "Rule", "Destination"]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    @pyqtSlot(dict)
    def _on_event(self, event_data: dict) -> None:
        """Handle incoming event (runs on GUI thread via signal)."""
        self._event_count += 1
        event_type = event_data.get("event_type", "unknown")

        if event_type == "file_moved":
            self._moved_count += 1
        elif event_type == "file_skipped":
            self._skipped_count += 1
        elif event_type == "error":
            self._error_count += 1

        # Update stats
        self._lbl_total.setText(f"Total: {self._event_count}")
        self._lbl_moved.setText(f"Moved: {self._moved_count}")
        self._lbl_skipped.setText(f"Skipped: {self._skipped_count}")
        self._lbl_errors.setText(f"Errors: {self._error_count}")

        # Trim table to prevent memory leak
        while self._table.rowCount() >= _MAX_TABLE_ROWS:
            self._table.removeRow(0)

        # Add row to table
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(
            event_data.get("timestamp", "")[:19]
        ))
        self._table.setItem(row, 1, QTableWidgetItem(event_type))
        self._table.setItem(row, 2, QTableWidgetItem(
            event_data.get("source_path", "").split("/")[-1].split("\\")[-1]
        ))
        self._table.setItem(row, 3, QTableWidgetItem(
            event_data.get("rule_name") or "—"
        ))
        self._table.setItem(row, 4, QTableWidgetItem(
            event_data.get("destination_path") or "—"
        ))

        # Auto-scroll to bottom
        self._table.scrollToBottom()
