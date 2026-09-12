"""Aircraft WebSocket connection manager.

Each connected client gets its own bounded :class:`asyncio.Queue`.  The
broadcast loop serialises the message *once* and drops it into every queue.
Each client's sender coroutine drains its own queue independently, so a slow
client can never block other clients — if a queue is full the message is
silently dropped for that client.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

logger = get_logger(__name__)

# Maximum messages buffered per client before dropping.
_CLIENT_QUEUE_SIZE = 64

# Heartbeat interval in seconds.
HEARTBEAT_INTERVAL = 15


@dataclass
class ClientConnection:
    """Wraps a WebSocket with a per-client send queue and metadata."""

    websocket: WebSocket
    client_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=_CLIENT_QUEUE_SIZE))
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages_sent: int = 0
    messages_dropped: int = 0


class AircraftConnectionManager:
    """Manages ``/ws/aircraft`` connections with non-blocking per-client queues.

    Usage (inside a route)::

        client = await manager.accept(websocket)
        try:
            await manager.client_loop(client)
        finally:
            manager.remove(client)
    """

    def __init__(self) -> None:
        self._clients: Dict[str, ClientConnection] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def accept(self, websocket: WebSocket) -> ClientConnection:
        """Accept the WebSocket handshake and register the client."""
        await websocket.accept()
        client = ClientConnection(websocket=websocket)
        self._clients[client.client_id] = client
        logger.info(
            "Client %s connected (total=%d)",
            client.client_id,
            len(self._clients),
        )
        return client

    def remove(self, client: ClientConnection) -> None:
        """Unregister a client after disconnect."""
        self._clients.pop(client.client_id, None)
        logger.info(
            "Client %s removed (sent=%d, dropped=%d, total=%d)",
            client.client_id,
            client.messages_sent,
            client.messages_dropped,
            len(self._clients),
        )

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def clients(self) -> list[ClientConnection]:
        return list(self._clients.values())

    # ------------------------------------------------------------------
    # Per-client loop (runs inside the route handler)
    # ------------------------------------------------------------------

    async def client_loop(self, client: ClientConnection) -> None:
        """Run the sender + receiver + heartbeat for one client until disconnect.

        This coroutine blocks until the client disconnects or errors.
        """
        sender_task = asyncio.create_task(
            self._sender(client), name=f"ws-sender-{client.client_id}"
        )
        heartbeat_task = asyncio.create_task(
            self._heartbeat(client), name=f"ws-heartbeat-{client.client_id}"
        )

        try:
            # Receiver loop — keeps the connection alive and reads client msgs.
            await self._receiver(client)
        finally:
            sender_task.cancel()
            heartbeat_task.cancel()
            # Suppress CancelledError from tasks
            for t in (sender_task, heartbeat_task):
                try:
                    await t
                except asyncio.CancelledError:
                    pass

    # ------------------------------------------------------------------
    # Broadcast (called from the state-update listener)
    # ------------------------------------------------------------------

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Enqueue *message* for every connected client.

        Serialisation happens once.  If a client's queue is full the message
        is dropped for that client only.
        """
        if not self._clients:
            return

        payload = json.dumps(message)
        drop_count = 0

        for client in list(self._clients.values()):
            try:
                client.queue.put_nowait(payload)
            except asyncio.QueueFull:
                client.messages_dropped += 1
                drop_count += 1

        if drop_count:
            logger.warning("Dropped message for %d slow client(s)", drop_count)

    async def broadcast_raw(self, payload: str) -> None:
        """Enqueue a pre-serialised string for every connected client."""
        if not self._clients:
            return

        for client in list(self._clients.values()):
            try:
                client.queue.put_nowait(payload)
            except asyncio.QueueFull:
                client.messages_dropped += 1

    # ------------------------------------------------------------------
    # Internal coroutines
    # ------------------------------------------------------------------

    async def _sender(self, client: ClientConnection) -> None:
        """Drain the client's queue and push messages over the WebSocket."""
        try:
            while True:
                payload = await client.queue.get()
                try:
                    await client.websocket.send_text(payload)
                    client.messages_sent += 1
                except Exception as e:
                    logger.error("Error sending to client %s: %s", client.client_id, e)
                    # Connection broken — exit so the route handler cleans up.
                    break
        except asyncio.CancelledError:
            pass

    async def _receiver(self, client: ClientConnection) -> None:
        """Read incoming messages until disconnect.

        We don't expect meaningful client→server messages on this endpoint
        but we must keep reading to detect disconnects and to consume
        WebSocket control frames.
        """
        try:
            while True:
                data = await client.websocket.receive_text()
                logger.debug("Client %s sent: %s", client.client_id, data[:120])
        except Exception:
            # WebSocketDisconnect or any receive error — exit cleanly.
            pass

    async def _heartbeat(self, client: ClientConnection) -> None:
        """Send periodic heartbeats so proxies / load-balancers keep the connection open."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                msg = json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                try:
                    client.queue.put_nowait(msg)
                except asyncio.QueueFull:
                    client.messages_dropped += 1
        except asyncio.CancelledError:
            pass


# Global singleton — imported by routes and the state listener.
aircraft_manager = AircraftConnectionManager()
