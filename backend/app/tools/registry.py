"""Central registry for aviation domain tools with MCP manifest generation and execution dispatcher."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.core.logging import get_logger
from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.tools.aircraft_tools import (
    GetAircraftHistoryTool,
    GetAircraftTool,
    GetFlightStatisticsTool,
    SearchAircraftInAreaTool,
    SearchAircraftTool,
)
from app.tools.airport_tools import (
    GetAircraftNearAirportTool,
    GetAirportTool,
    GetAirportTrafficTool,
)
from app.tools.base import BaseTool

logger = get_logger(__name__)


class ToolRegistry:
    """Catalog and dispatcher for all agent-callable aviation domain tools.

    Enforces that tools can only be invoked through validated contracts and provides
    standard Model Context Protocol (MCP) tool declarations for LLM agent integration.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a domain tool instance."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool registration for '{tool.name}'")
        self._tools[tool.name] = tool
        logger.info(f"Registered aviation domain tool: '{tool.name}'")

    def get(self, name: str) -> Optional[BaseTool]:
        """Lookup tool by unique name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """Return all registered domain tool instances."""
        return list(self._tools.values())

    def list_names(self) -> List[str]:
        """Return names of all registered domain tools."""
        return list(self._tools.keys())

    async def execute(self, tool_name: str, params: dict[str, Any] | BaseModel) -> BaseModel:
        """Execute a registered tool by name with parameter validation.

        Args:
            tool_name: The registered tool identifier.
            params: Dictionary of arguments or pre-validated Pydantic model.

        Returns:
            Pydantic model representing the tool output.

        Raises:
            KeyError: If tool_name is not registered.
            ValidationError: If input parameters violate the tool's schema.
        """
        tool = self.get(tool_name)
        if not tool:
            available = ", ".join(self._tools.keys())
            raise KeyError(
                f"Unknown tool '{tool_name}'. Available tools: [{available}]"
            )
        return await tool.run(params)

    def get_mcp_manifest(self) -> List[dict[str, Any]]:
        """Generate MCP-compliant tool manifest containing all tool declarations."""
        return [tool.to_mcp_tool_definition() for tool in self._tools.values()]


def create_default_registry(
    aircraft_service: AircraftService,
    airport_service: AirportService,
) -> ToolRegistry:
    """Build and return a ToolRegistry populated with all 8 core aviation domain tools."""
    registry = ToolRegistry()

    # 1. Aircraft search & tracking
    registry.register(SearchAircraftTool(aircraft_service))
    registry.register(GetAircraftTool(aircraft_service))
    registry.register(GetAircraftHistoryTool(aircraft_service))
    registry.register(SearchAircraftInAreaTool(aircraft_service))
    registry.register(GetFlightStatisticsTool(aircraft_service))

    # 2. Airport and terminal airspace
    registry.register(GetAirportTool(airport_service))
    registry.register(GetAircraftNearAirportTool(airport_service))
    registry.register(GetAirportTrafficTool(airport_service))

    return registry
