"""WebSocket route handlers.

``/ws``             — generic heartbeat endpoint (kept for health-check tooling).
``/ws/aircraft``    — real-time aircraft state updates.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.ws.aircraft_manager import aircraft_manager
from app.ws.manager import manager

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])


# ------------------------------------------------------------------
# /ws — lightweight heartbeat (unchanged from bootstrap)
# ------------------------------------------------------------------

async def _send_heartbeat(websocket: WebSocket) -> None:
    """Send heartbeat message periodically on the generic /ws endpoint."""
    try:
        while True:
            await asyncio.sleep(15)
            if websocket.client_state == WebSocketState.CONNECTED:
                await manager.send_personal(
                    {"type": "heartbeat", "timestamp": datetime.now(UTC).isoformat()},
                    websocket,
                )
            else:
                break
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("Heartbeat error: %s", exc)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Generic WebSocket endpoint with heartbeat."""
    await manager.connect(websocket)
    heartbeat_task = asyncio.create_task(_send_heartbeat(websocket))
    try:
        while True:
            data = await websocket.receive_text()
            logger.info("Received message on /ws: %s", data)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /ws")
    finally:
        manager.disconnect(websocket)
        heartbeat_task.cancel()


# ------------------------------------------------------------------
# /ws/aircraft — real-time aircraft updates
# ------------------------------------------------------------------

from fastapi import Depends
import redis.asyncio as aioredis
from app.api.routes.aircraft import get_redis
import json

@router.websocket("/ws/aircraft")
async def aircraft_websocket(
    websocket: WebSocket,
    redis: aioredis.Redis = Depends(get_redis)
) -> None:
    """Stream aircraft state diffs to the client.

    On connect the client receives an initial ``aircraft_update`` snapshot
    with all currently known aircraft in the ``added`` field.  Subsequent
    messages contain only the diff (added / updated / removed).
    """
    client = await aircraft_manager.accept(websocket)
    try:
        # Send initial snapshot immediately
        raw_data = await redis.hgetall("aircraft:states")
        
        added_list = []
        for _key, val in raw_data.items():
            try:
                # We can just decode the JSON and send it raw to save parsing overhead
                added_list.append(json.loads(val))
            except Exception:
                pass
                
        snapshot_msg = {
            "type": "aircraft_update",
            "timestamp": datetime.now(UTC).isoformat(),
            "added": added_list,
            "updated": [],
            "removed": []
        }
        
        # Enqueue the snapshot to the client's queue so it gets sent by the sender task
        client.queue.put_nowait(json.dumps(snapshot_msg))
        
        await aircraft_manager.client_loop(client)
    except WebSocketDisconnect:
        logger.info("Client %s disconnected from /ws/aircraft", client.client_id)
    except Exception as exc:
        logger.warning("Client %s error: %s", client.client_id, exc)
    finally:
        aircraft_manager.remove(client)
