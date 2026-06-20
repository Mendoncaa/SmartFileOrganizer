"""Windows Service adapter — runs the core service as a Windows Service."""

from __future__ import annotations

import sys


def is_windows() -> bool:
    return sys.platform == "win32"


if is_windows():
    try:
        import servicemanager
        import win32event
        import win32service
        import win32serviceutil

        class SmartFileOrganizerService(win32serviceutil.ServiceFramework):
            """Windows Service wrapper for the Smart File Organizer core."""

            _svc_name_ = "SmartFileOrganizer"
            _svc_display_name_ = "Smart File Organizer"
            _svc_description_ = (
                "Monitors folders and automatically organizes files using rules + AI"
            )

            def __init__(self, args):
                super().__init__(args)
                self.stop_event = win32event.CreateEvent(None, 0, 0, None)
                self._service = None

            def SvcStop(self):
                """Handle stop request."""
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                win32event.SetEvent(self.stop_event)
                if self._service:
                    self._service.stop()

            def SvcDoRun(self):
                """Main service entry point."""
                from src.core.main import CoreService

                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""),
                )

                self._service = CoreService()
                self._service.start()

                # Wait for stop signal
                win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

    except ImportError:
        # pywin32 not installed — provide stub
        SmartFileOrganizerService = None  # type: ignore[assignment, misc]
else:
    SmartFileOrganizerService = None  # type: ignore[assignment, misc]
