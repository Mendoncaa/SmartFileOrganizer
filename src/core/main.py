"""Core service entry point — wires everything together and starts monitoring."""

from __future__ import annotations

from pathlib import Path

from src.core.debouncer import FileDebouncer
from src.core.dispatcher import Dispatcher
from src.core.ipc_server import IPCServer
from src.core.mover import UndoLog
from src.core.watcher import FolderWatcher
from src.shared.config import load_rules, load_settings
from src.shared.constants import ServiceCommand
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)


class CoreService:
    """Main orchestrator that wires all components together."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or Path.cwd()
        self._watcher: FolderWatcher | None = None
        self._debouncer: FileDebouncer | None = None
        self._dispatcher: Dispatcher | None = None
        self._ipc_server: IPCServer | None = None
        self._paused = False

    def start(self) -> None:
        """Initialize and start all components."""
        # Load configuration
        settings = load_settings(base_dir=self._config_dir)
        rules = load_rules(base_dir=self._config_dir)

        # Setup logging
        setup_logging(settings.logging)
        logger.info("core_service_starting", config_dir=str(self._config_dir))

        # Initialize undo log
        undo_log = UndoLog(self._config_dir / "data" / "undo.jsonl")

        # Initialize dispatcher
        self._dispatcher = Dispatcher(rules, settings, undo_log)

        # Initialize IPC server
        self._ipc_server = IPCServer()
        self._ipc_server.register_command_handler(ServiceCommand.PAUSE, self._handle_pause)
        self._ipc_server.register_command_handler(ServiceCommand.RESUME, self._handle_resume)
        self._ipc_server.register_command_handler(ServiceCommand.STATUS, self._handle_status)
        self._ipc_server.register_command_handler(
            ServiceCommand.RELOAD_CONFIG, self._handle_reload
        )
        self._ipc_server.start()

        # Wire dispatcher events to IPC publisher
        self._dispatcher.add_event_listener(self._ipc_server.publish_event)

        # Initialize debouncer → dispatcher
        self._debouncer = FileDebouncer(
            callback=self._process_file,
            delay=settings.debounce_seconds,
        )

        # Initialize watcher → debouncer
        folders = [
            (wf.path, wf.recursive)
            for wf in settings.watch_folders
            if wf.enabled
        ]
        self._watcher = FolderWatcher(folders=folders, callback=self._debouncer.file_detected)
        self._watcher.start()

        logger.info("core_service_started", watch_folders=len(folders))

    def stop(self) -> None:
        """Stop all components gracefully."""
        if self._watcher:
            self._watcher.stop()
        if self._debouncer:
            self._debouncer.cancel_all()
        if self._ipc_server:
            self._ipc_server.stop()
        logger.info("core_service_stopped")

    def _process_file(self, file_path: Path) -> None:
        """Process a file (called by debouncer when file is stable)."""
        if self._paused:
            logger.debug("skipped_while_paused", file=file_path.name)
            return
        if self._dispatcher:
            self._dispatcher.process_file(file_path)

    def _handle_pause(self) -> str:
        self._paused = True
        logger.info("service_paused")
        return "paused"

    def _handle_resume(self) -> str:
        self._paused = False
        logger.info("service_resumed")
        return "resumed"

    def _handle_status(self) -> dict:
        return {
            "paused": self._paused,
            "watching": self._watcher.is_running if self._watcher else False,
        }

    def _handle_reload(self) -> str:
        """Reload rules and settings from disk."""
        try:
            from src.shared.config import load_rules, load_settings

            settings = load_settings(base_dir=self._config_dir)
            rules = load_rules(base_dir=self._config_dir)

            undo_log = UndoLog(self._config_dir / "data" / "undo.jsonl")
            self._dispatcher = Dispatcher(rules, settings, undo_log)
            if self._ipc_server:
                self._dispatcher.add_event_listener(self._ipc_server.publish_event)

            logger.info("config_reloaded_successfully")
            return "reloaded"
        except Exception as e:
            logger.error("config_reload_failed", error=str(e))
            return f"error: {e}"


def main() -> None:
    """Entry point for the core service."""
    import signal

    service = CoreService()
    service.start()

    # Handle graceful shutdown
    def shutdown(signum, frame):
        service.stop()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep running
    import threading

    stop_event = threading.Event()
    try:
        stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        service.stop()


if __name__ == "__main__":
    main()
