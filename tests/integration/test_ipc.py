"""Integration tests for IPC server↔client communication."""

import time
from pathlib import Path

from src.core.ipc_server import IPCServer
from src.shared.constants import EventType, ServiceCommand
from src.shared.models import FileEvent
from src.ui.ipc_client import IPCClient


class TestIPCRoundTrip:
    """Test IPC communication between server and client."""

    def test_command_round_trip(self):
        """Client sends command, server responds."""
        server = IPCServer(pub_port=15578, rep_port=15577)
        client = IPCClient(pub_port=15578, rep_port=15577)

        # Register a handler
        paused = {"value": False}

        def handle_pause():
            paused["value"] = True
            return "paused"

        server.register_command_handler(ServiceCommand.PAUSE, handle_pause)

        server.start()
        client.connect()
        time.sleep(0.3)  # Allow connections to establish

        try:
            response = client.send_command(ServiceCommand.PAUSE)
            assert response["status"] == "ok"
            assert response["result"] == "paused"
            assert paused["value"] is True
        finally:
            client.disconnect()
            server.stop()

    def test_event_publishing(self):
        """Server publishes event, client receives it."""
        server = IPCServer(pub_port=15678, rep_port=15677)
        client = IPCClient(pub_port=15678, rep_port=15677)

        received_events: list[dict] = []
        client.on_event(received_events.append)

        server.start()
        client.connect()
        time.sleep(0.5)  # Allow SUB to connect (ZMQ slow joiner)

        try:
            # Publish an event
            event = FileEvent(
                event_type=EventType.FILE_MOVED,
                source_path=Path("/downloads/file.pdf"),
                destination_path=Path("/docs/file.pdf"),
                rule_name="PDFs",
            )
            server.publish_event(event)
            time.sleep(0.5)

            assert len(received_events) >= 1
            assert received_events[0]["event_type"] == "file_moved"
            assert received_events[0]["rule_name"] == "PDFs"
        finally:
            client.disconnect()
            server.stop()

    def test_unknown_command(self):
        """Server responds with error for unknown commands."""
        server = IPCServer(pub_port=15778, rep_port=15777)
        client = IPCClient(pub_port=15778, rep_port=15777)

        server.start()
        client.connect()
        time.sleep(0.3)

        try:
            response = client.send_command(ServiceCommand.SHUTDOWN)
            assert response["status"] == "error"
            assert "Unknown command" in response["message"]
        finally:
            client.disconnect()
            server.stop()

    def test_multiple_commands(self):
        """Multiple commands in sequence work correctly."""
        server = IPCServer(pub_port=15878, rep_port=15877)
        client = IPCClient(pub_port=15878, rep_port=15877)

        state = {"paused": False}

        def handle_pause():
            state["paused"] = True
            return "paused"

        def handle_resume():
            state["paused"] = False
            return "resumed"

        def handle_status():
            return {"paused": state["paused"]}

        server.register_command_handler(ServiceCommand.PAUSE, handle_pause)
        server.register_command_handler(ServiceCommand.RESUME, handle_resume)
        server.register_command_handler(ServiceCommand.STATUS, handle_status)

        server.start()
        client.connect()
        time.sleep(0.3)

        try:
            r1 = client.send_command(ServiceCommand.PAUSE)
            assert r1["status"] == "ok"
            assert state["paused"] is True

            r2 = client.send_command(ServiceCommand.STATUS)
            assert r2["result"]["paused"] is True

            r3 = client.send_command(ServiceCommand.RESUME)
            assert r3["status"] == "ok"
            assert state["paused"] is False
        finally:
            client.disconnect()
            server.stop()

    def test_server_start_stop(self):
        """Server starts and stops cleanly."""
        server = IPCServer(pub_port=15978, rep_port=15977)
        server.start()
        time.sleep(0.2)
        server.stop()
        # Should not raise
