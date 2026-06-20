"""IPC Client — subscribes to events and sends commands to the core service."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

import zmq

from src.shared.constants import IPC_DEFAULT_PORT, IPC_PUB_PORT, ServiceCommand
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class IPCClient:
    """ZeroMQ-based IPC client for the UI.

    Provides:
    - SUB socket: receives FileEvent notifications from the core service
    - REQ socket: sends commands (pause, resume, reload) to the core service

    Args:
        pub_port: Port to subscribe to events on.
        rep_port: Port to send commands to.
    """

    def __init__(
        self,
        pub_port: int = IPC_PUB_PORT,
        rep_port: int = IPC_DEFAULT_PORT,
    ) -> None:
        self._pub_port = pub_port
        self._rep_port = rep_port
        self._context: zmq.Context | None = None
        self._sub_socket: zmq.Socket | None = None
        self._req_socket: zmq.Socket | None = None
        self._running = False
        self._event_thread: threading.Thread | None = None
        self._event_callbacks: list[Callable[[dict], None]] = []

    def on_event(self, callback: Callable[[dict], None]) -> None:
        """Register a callback to receive event notifications.

        Args:
            callback: Function that receives a dict with event data.
        """
        self._event_callbacks.append(callback)

    def connect(self) -> None:
        """Connect to the core service."""
        if self._running:
            return

        self._context = zmq.Context()

        # SUB socket for receiving events
        self._sub_socket = self._context.socket(zmq.SUB)
        self._sub_socket.connect(f"tcp://127.0.0.1:{self._pub_port}")
        self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all

        # REQ socket for sending commands
        self._req_socket = self._context.socket(zmq.REQ)
        self._req_socket.connect(f"tcp://127.0.0.1:{self._rep_port}")
        self._req_socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5s timeout

        self._running = True

        # Start event listener in background
        self._event_thread = threading.Thread(
            target=self._event_loop,
            daemon=True,
            name="ipc-event-loop",
        )
        self._event_thread.start()

        logger.info("ipc_client_connected")

    def disconnect(self) -> None:
        """Disconnect from the core service."""
        self._running = False

        if self._sub_socket:
            self._sub_socket.close(linger=100)
            self._sub_socket = None

        if self._req_socket:
            self._req_socket.close(linger=100)
            self._req_socket = None

        if self._context:
            self._context.term()
            self._context = None

        if self._event_thread and self._event_thread.is_alive():
            self._event_thread.join(timeout=2)

        logger.info("ipc_client_disconnected")

    def send_command(self, command: ServiceCommand) -> dict:
        """Send a command to the core service and wait for response.

        Args:
            command: The command to send.

        Returns:
            Response dict from the server.
        """
        if not self._running or self._req_socket is None:
            return {"status": "error", "message": "Not connected"}

        try:
            message = json.dumps({"command": str(command)})
            self._req_socket.send_string(message)
            response = self._req_socket.recv_string()
            return json.loads(response)
        except zmq.ZMQError as e:
            return {"status": "error", "message": f"ZMQ error: {e}"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid response from server"}

    def _event_loop(self) -> None:
        """Background loop that receives events from the PUB socket."""
        poller = zmq.Poller()
        poller.register(self._sub_socket, zmq.POLLIN)

        while self._running:
            try:
                sockets = dict(poller.poll(timeout=500))
                if self._sub_socket in sockets:
                    message = self._sub_socket.recv_string()
                    event_data = json.loads(message)
                    self._dispatch_event(event_data)
            except zmq.ZMQError:
                if self._running:
                    logger.debug("event_loop_zmq_error")
                break
            except json.JSONDecodeError:
                continue

    def _dispatch_event(self, event_data: dict) -> None:
        """Dispatch an event to all registered callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(event_data)
            except Exception:
                logger.exception("event_callback_error")
