"""IPC Server — publishes events and accepts commands via ZeroMQ."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import zmq

from src.shared.constants import IPC_DEFAULT_PORT, IPC_PUB_PORT, ServiceCommand
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.shared.models import FileEvent

logger = get_logger(__name__)


class IPCServer:
    """ZeroMQ-based IPC server for the core service.

    Provides two channels:
    - PUB socket: broadcasts FileEvent notifications to UI clients
    - REP socket: receives commands (pause, resume, reload, status) from UI

    Args:
        pub_port: Port for the PUB socket (events broadcast).
        rep_port: Port for the REP socket (command handling).
    """

    def __init__(
        self,
        pub_port: int = IPC_PUB_PORT,
        rep_port: int = IPC_DEFAULT_PORT,
    ) -> None:
        self._pub_port = pub_port
        self._rep_port = rep_port
        self._context: zmq.Context | None = None
        self._pub_socket: zmq.Socket | None = None
        self._rep_socket: zmq.Socket | None = None
        self._running = False
        self._command_thread: threading.Thread | None = None
        self._command_handlers: dict[str, callable] = {}

    def register_command_handler(self, command: ServiceCommand, handler: callable) -> None:
        """Register a handler for a specific command."""
        self._command_handlers[str(command)] = handler

    def start(self) -> None:
        """Start the IPC server (PUB + REP sockets)."""
        if self._running:
            return

        self._context = zmq.Context()

        # PUB socket for broadcasting events
        self._pub_socket = self._context.socket(zmq.PUB)
        self._pub_socket.bind(f"tcp://127.0.0.1:{self._pub_port}")

        # REP socket for receiving commands
        self._rep_socket = self._context.socket(zmq.REP)
        self._rep_socket.bind(f"tcp://127.0.0.1:{self._rep_port}")

        self._running = True

        # Start command listener in a background thread
        self._command_thread = threading.Thread(
            target=self._command_loop,
            daemon=True,
            name="ipc-command-loop",
        )
        self._command_thread.start()

        logger.info(
            "ipc_server_started",
            pub_port=self._pub_port,
            rep_port=self._rep_port,
        )

    def stop(self) -> None:
        """Stop the IPC server and clean up resources."""
        self._running = False

        if self._pub_socket:
            self._pub_socket.close(linger=100)
            self._pub_socket = None

        if self._rep_socket:
            self._rep_socket.close(linger=100)
            self._rep_socket = None

        if self._context:
            self._context.term()
            self._context = None

        if self._command_thread and self._command_thread.is_alive():
            self._command_thread.join(timeout=2)

        logger.info("ipc_server_stopped")

    def publish_event(self, event: FileEvent) -> None:
        """Broadcast a FileEvent to all connected subscribers.

        Args:
            event: The file event to publish.
        """
        if not self._running or self._pub_socket is None:
            return

        try:
            message = json.dumps({
                "event_type": str(event.event_type),
                "source_path": str(event.source_path),
                "destination_path": str(event.destination_path) if event.destination_path else None,
                "rule_name": event.rule_name,
                "timestamp": event.timestamp.isoformat(),
                "error_message": event.error_message,
            })
            self._pub_socket.send_string(message, zmq.NOBLOCK)
        except zmq.ZMQError as e:
            logger.debug("publish_event_failed", error=str(e))

    def _command_loop(self) -> None:
        """Background loop that listens for commands on the REP socket."""
        poller = zmq.Poller()
        poller.register(self._rep_socket, zmq.POLLIN)

        while self._running:
            try:
                sockets = dict(poller.poll(timeout=500))  # 500ms poll timeout
                if self._rep_socket in sockets:
                    message = self._rep_socket.recv_string()
                    response = self._handle_command(message)
                    self._rep_socket.send_string(response)
            except zmq.ZMQError:
                if self._running:
                    logger.debug("command_loop_zmq_error")
                break

    def _handle_command(self, raw_message: str) -> str:
        """Parse and execute a command, returning a JSON response."""
        try:
            data = json.loads(raw_message)
            command = data.get("command", "")
        except (json.JSONDecodeError, AttributeError):
            return json.dumps({"status": "error", "message": "Invalid JSON"})

        handler = self._command_handlers.get(command)
        if handler is None:
            return json.dumps({"status": "error", "message": f"Unknown command: {command}"})

        try:
            result = handler()
            return json.dumps({"status": "ok", "result": result})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
