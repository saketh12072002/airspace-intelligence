import json
from typing import Set
from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        self.active_connections.discard(websocket)

    async def send_personal(self, message: dict, websocket: WebSocket) -> None:
        """Send a message to a specific WebSocket connection."""
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict) -> None:
        """Send a message to all active WebSocket connections."""
        msg_str = json.dumps(message)
        dead_connections = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception:
                dead_connections.add(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)

# Global manager instance
manager = ConnectionManager()
