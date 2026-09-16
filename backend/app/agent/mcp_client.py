"""Official Model Context Protocol (MCP) client for the Flight Search Agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from app.core.logging import get_logger
from app.mcp.adapter import create_mcp_server
from app.tools.registry import ToolRegistry

logger = get_logger(__name__)


class FlightSearchMCPClient:
    """Client interface for interacting with the Airspace Intelligence MCP Server.

    Can operate against an in-process MCPServer instance for high performance and zero
    IPC overhead, or connect via standard MCP transport sessions.
    """

    def __init__(
        self,
        mcp_server: Optional[MCPServer] = None,
        registry: Optional[ToolRegistry] = None,
    ) -> None:
        if mcp_server is not None:
            self._server = mcp_server
        elif registry is not None:
            self._server = create_mcp_server(registry)
        else:
            raise ValueError("FlightSearchMCPClient requires either an MCPServer or ToolRegistry instance.")

        self._cached_tools: Optional[List[dict]] = None

    async def discover_tools(self) -> List[dict]:
        """Discover available tools and their JSON schemas from the MCP server."""
        if self._cached_tools is None:
            raw_tools = await self._server.list_tools()
            self._cached_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in raw_tools
            ]
            logger.info("Discovered %d tools from MCP server", len(self._cached_tools))
        return self._cached_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Invoke an MCP tool with validated arguments and return structured results.

        Args:
            tool_name: Name of the registered MCP tool.
            arguments: Dictionary of arguments conforming to the tool's input schema.

        Returns:
            Structured content dictionary or primitive from the MCP execution.

        Raises:
            ToolError: If execution fails or parameters fail validation.
        """
        logger.debug("Executing MCP tool '%s' with args: %s", tool_name, arguments)
        try:
            call_result = await self._server.call_tool(tool_name, arguments)
            if call_result.is_error:
                error_msg = (
                    call_result.content[0].text
                    if call_result.content
                    else "Unknown MCP tool error"
                )
                raise ToolError(error_msg)

            # Return structured content if available, or fall back to parsing text
            if call_result.structured_content is not None:
                return call_result.structured_content
            if call_result.content and hasattr(call_result.content[0], "text"):
                import json
                try:
                    return json.loads(call_result.content[0].text)
                except Exception:
                    return call_result.content[0].text
            return None
        except ToolError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error executing MCP tool '%s'", tool_name)
            raise ToolError(f"Error executing tool '{tool_name}': {str(exc)}") from exc
