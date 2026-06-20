"""Unix daemon adapter — runs the core service as a systemd-compatible daemon."""

from __future__ import annotations

import signal
import sys
from pathlib import Path


def run_daemon(config_dir: Path | None = None) -> None:
    """Run the core service as a foreground daemon (systemd handles daemonization).

    This is designed to be called by systemd with Type=simple.
    systemd manages the process lifecycle, so we just need to:
    - Start the service
    - Handle SIGTERM for graceful shutdown
    - Block until stopped

    Args:
        config_dir: Override for configuration directory.
    """
    from src.core.main import CoreService

    service = CoreService(config_dir=config_dir)
    service.start()

    def shutdown(signum, frame):
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Block forever (systemd sends SIGTERM to stop)
    import threading

    threading.Event().wait()


SYSTEMD_UNIT = """\
[Unit]
Description=Smart File Organizer
After=network.target

[Service]
Type=simple
ExecStart={exec_path}
Restart=on-failure
RestartSec=5
User={user}
WorkingDirectory={work_dir}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""


def generate_systemd_unit(
    exec_path: str = "/usr/local/bin/sfo-core",
    user: str = "",
    work_dir: str = "",
) -> str:
    """Generate a systemd unit file content.

    Args:
        exec_path: Path to the executable.
        user: Unix user to run the service as.
        work_dir: Working directory for the service.

    Returns:
        The systemd unit file content.
    """
    import os

    if not user:
        user = os.environ.get("USER", "root")
    if not work_dir:
        work_dir = str(Path.home())

    return SYSTEMD_UNIT.format(
        exec_path=exec_path,
        user=user,
        work_dir=work_dir,
    )
