"""System tray icon — provides quick access to the Smart File Organizer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.shared.constants import ServiceCommand
from src.shared.logging import get_logger
from src.ui.dashboard import DashboardWindow
from src.ui.rules_editor import RulesEditorWindow

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
        # Keep references to prevent GC from destroying windows
        self._dashboard: DashboardWindow | None = None
        self._rules_editor: RulesEditorWindow | None = None

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

        dashboard_action = QAction("Open Dashboard", app)
        dashboard_action.triggered.connect(self._open_dashboard)
        menu.addAction(dashboard_action)

        rules_action = QAction("Edit Rules", app)
        rules_action.triggered.connect(self._open_rules_editor)
        menu.addAction(rules_action)

        menu.addSeparator()

        self._pause_action = QAction("Pause", app)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

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

    def _open_dashboard(self) -> None:
        """Open or focus the dashboard window."""
        if self._dashboard is None:
            self._dashboard = DashboardWindow(self._client)
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()

    def _open_rules_editor(self) -> None:
        """Open or focus the rules editor window."""
        if self._rules_editor is None:
            self._rules_editor = RulesEditorWindow(Path("config/rules.yaml"))
        self._rules_editor.show()
        self._rules_editor.raise_()
        self._rules_editor.activateWindow()

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
