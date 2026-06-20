"""UI entry point — launches the system tray and dashboard."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from src.shared.logging import get_logger, setup_logging
from src.shared.models import LoggingSettings
from src.ui.ipc_client import IPCClient
from src.ui.tray import SystemTray

logger = get_logger(__name__)


def main() -> None:
    """Launch the Smart File Organizer UI."""
    setup_logging(LoggingSettings(level="INFO"))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Connect to core service
    client = IPCClient()
    client.connect()

    # Setup tray icon
    tray = SystemTray(client)
    tray.setup(app)

    logger.info("ui_started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
