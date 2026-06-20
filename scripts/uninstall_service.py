"""Uninstall the Smart File Organizer system service."""

from __future__ import annotations

import sys


def uninstall_windows_service() -> None:
    """Uninstall the Windows Service."""
    try:
        import win32serviceutil

        from src.core.service.windows_service import SmartFileOrganizerService

        if SmartFileOrganizerService is None:
            print("ERROR: Service not available on this platform.")
            sys.exit(1)

        win32serviceutil.HandleCommandLine(SmartFileOrganizerService, argv=["", "remove"])
        print("Service uninstalled successfully.")
    except ImportError:
        print("ERROR: pywin32 is required.")
        sys.exit(1)


def uninstall_linux_service() -> None:
    """Instructions for removing systemd service."""
    print("To uninstall the systemd service:")
    print("  sudo systemctl stop smart-file-organizer")
    print("  sudo systemctl disable smart-file-organizer")
    print("  sudo rm /etc/systemd/system/smart-file-organizer.service")
    print("  sudo systemctl daemon-reload")


def main() -> None:
    """Auto-detect platform and uninstall service."""
    if sys.platform == "win32":
        uninstall_windows_service()
    else:
        uninstall_linux_service()


if __name__ == "__main__":
    main()
