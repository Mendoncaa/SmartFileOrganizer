"""Install the Smart File Organizer as a system service."""

from __future__ import annotations

import sys
from pathlib import Path


def install_windows_service() -> None:
    """Install as a Windows Service (requires admin privileges)."""
    try:
        import win32serviceutil

        from src.core.service.windows_service import SmartFileOrganizerService

        if SmartFileOrganizerService is None:
            print("ERROR: pywin32 is required. Install with: pip install pywin32")
            sys.exit(1)

        win32serviceutil.HandleCommandLine(SmartFileOrganizerService, argv=["", "install"])
        print("Service installed successfully.")
        print("Start with: net start SmartFileOrganizer")
    except ImportError:
        print("ERROR: pywin32 is required. Install with: pip install pywin32")
        sys.exit(1)


def install_linux_service() -> None:
    """Generate and install systemd unit file."""
    from src.core.service.unix_daemon import generate_systemd_unit

    unit_content = generate_systemd_unit()
    unit_path = Path("/etc/systemd/system/smart-file-organizer.service")

    print(f"Systemd unit file content:\n\n{unit_content}")
    print(f"\nTo install, save to: {unit_path}")
    print("Then run:")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable smart-file-organizer")
    print("  sudo systemctl start smart-file-organizer")


def main() -> None:
    """Auto-detect platform and install service."""
    if sys.platform == "win32":
        install_windows_service()
    else:
        install_linux_service()


if __name__ == "__main__":
    main()
