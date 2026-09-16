"""Standalone Model Context Protocol (MCP) server executable for Airspace Intelligence.

Usage:
    # Run over standard I/O (default, for Claude Desktop, Cursor, local agent runners):
    python -m app.mcp.server --transport stdio

    # Run over Server-Sent Events (SSE) with Streamable HTTP on port 8001:
    python -m app.mcp.server --transport sse --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.mcp.adapter import create_mcp_server
from app.repositories.aircraft_repo import InMemoryAircraftRepository, RedisAircraftRepository
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository
from app.tools.registry import create_default_registry

setup_logging()
logger = get_logger("airspace.mcp")


async def bootstrap_repositories() -> tuple[AircraftService, AirportService, Optional[aioredis.Redis]]:
    """Initialize repository backends with resilient fallback to in-memory stores."""
    settings = get_settings()
    redis_client: Optional[aioredis.Redis] = None

    try:
        candidate_redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=False,
            socket_connect_timeout=2.0,
        )
        # Quick ping to verify connectivity
        await asyncio.wait_for(candidate_redis.ping(), timeout=2.0)
        redis_client = candidate_redis
        logger.info("MCP server connected to Redis at %s", settings.redis_url)
        aircraft_repo = RedisAircraftRepository(candidate_redis)
        history_repo = HistoryRepository(candidate_redis)
    except Exception as exc:
        logger.warning(
            "Redis connection unavailable (%s). Falling back to in-memory aircraft repository for MCP server.",
            exc,
        )
        if candidate_redis:
            try:
                await candidate_redis.aclose()
            except Exception:
                pass
        aircraft_repo = InMemoryAircraftRepository()
        history_repo = HistoryRepository()

    airport_repo = AirportRepository()
    aircraft_service = AircraftService(aircraft_repo, history_repo)
    airport_service = AirportService(airport_repo, aircraft_repo)

    return aircraft_service, airport_service, redis_client


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Airspace Intelligence Model Context Protocol (MCP) Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol: 'stdio' for standard I/O (default) or 'sse' for Server-Sent Events / HTTP",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind host for SSE transport (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Bind port for SSE transport (default: 8001)",
    )
    parser.add_argument(
        "--sse-path",
        default="/sse",
        help="Path for SSE connection endpoint (default: /sse)",
    )
    parser.add_argument(
        "--message-path",
        default="/messages/",
        help="Path for incoming client messages (default: /messages/)",
    )

    args = parser.parse_args()

    aircraft_svc, airport_svc, redis_client = await bootstrap_repositories()
    tool_registry = create_default_registry(aircraft_svc, airport_svc)
    mcp_server = create_mcp_server(tool_registry)

    logger.info(
        "Starting Airspace Intelligence MCP Server (transport=%s, tools=%d)",
        args.transport,
        len(tool_registry.list_tools()),
    )

    try:
        if args.transport == "stdio":
            await mcp_server.run_stdio_async()
        elif args.transport == "sse":
            logger.info("SSE server listening on http://%s:%d%s", args.host, args.port, args.sse_path)
            await mcp_server.run_sse_async(
                host=args.host,
                port=args.port,
                sse_path=args.sse_path,
                message_path=args.message_path,
            )
    finally:
        if redis_client:
            await redis_client.aclose()
        logger.info("Airspace Intelligence MCP server shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("MCP server stopped by user signal")
        sys.exit(0)
