"""System tray icon — provides quick access to the Smart File Organizer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.shared.constants import ServiceCommand
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.ui.ipc_client import IPCClient

logger = get_logger(__name__)


class SystemTray:
    """System tray icon with context menu for controlling the organizer.

    Args:
        ipc_client: Connected IPC client for sending commands.
    """

    def __init__(self, ipc_client: IPCClient) -> None:
        self._client = ipc_client
        self._app: QApplication | None = None
        self._tray: QSystemTrayIcon | None = None
        self._paused = False

    def setup(self, app: QApplication) -> None:
        """Set up the tray icon and menu."""
        self._app = app

        # Create tray icon
        self._tray = QSystemTrayIcon(app)
        self._tray.setToolTip("Smart File Organizer")

        # Set default icon (using a built-in icon as placeholder)
        icon = QIcon.fromTheme("folder")
        if icon.isNull():
            icon = app.style().standardIcon(app.style().StandardPixmap.SP_DirIcon)
        self._tray.setIcon(icon)

        # Create context menu
        menu = QMenu()

        self._pause_action = QAction("Pause", app)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        status_action = QAction("Status", app)
        status_action.triggered.connect(self._show_status)
        menu.addAction(status_action)

        reload_action = QAction("Reload Config", app)
        reload_action.triggered.connect(self._reload_config)
        menu.addAction(reload_action)

        menu.addSeparator()

        quit_action = QAction("Quit", app)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.show()

        logger.info("tray_icon_shown")

    def _toggle_pause(self) -> None:
        """Toggle between pause and resume."""
        if self._paused:
            response = self._client.send_command(ServiceCommand.RESUME)
            if response.get("status") == "ok":
                self._paused = False
                self._pause_action.setText("Pause")
                self._tray.showMessage(
                    "Smart File Organizer",
                    "Resumed file monitoring",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
        else:
            response = self._client.send_command(ServiceCommand.PAUSE)
            if response.get("status") == "ok":
                self._paused = True
                self._pause_action.setText("Resume")
                self._tray.showMessage(
                    "Smart File Organizer",
                    "Paused file monitoring",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )

    def _show_status(self) -> None:
        """Show current service status as a notification."""
        response = self._client.send_command(ServiceCommand.STATUS)
        if response.get("status") == "ok":
            result = response.get("result", {})
            msg = f"Status: {'Paused' if result.get('paused') else 'Running'}"
        else:
            msg = f"Error: {response.get('message', 'unknown')}"

        self._tray.showMessage(
            "Smart File Organizer",
            msg,
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _reload_config(self) -> None:
        """Request the core service to reload configuration."""
        response = self._client.send_command(ServiceCommand.RELOAD_CONFIG)
        if response.get("status") == "ok":
            self._tray.showMessage(
                "Smart File Organizer",
                "Configuration reloaded",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def _quit(self) -> None:
        """Quit the UI application."""
        self._client.disconnect()
        if self._app:
            self._app.quit()
