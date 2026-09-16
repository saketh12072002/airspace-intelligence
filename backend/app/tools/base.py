"""BaseTool contract for aviation domain tools with MCP tool schema export."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, Type, TypeVar
from pydantic import BaseModel

TInput = TypeVar("TInput", bound=BaseModel)
TOutput = TypeVar("TOutput", bound=BaseModel)


class BaseTool(ABC, Generic[TInput, TOutput]):
    """Generic base class for deterministic aviation domain tools.

    Provides strict input/output Pydantic validation and automatic
    Model Context Protocol (MCP) tool schema generation.
    """

    name: str
    description: str
    input_schema: Type[TInput]
    output_schema: Type[TOutput]

    @abstractmethod
    async def execute(self, params: TInput) -> TOutput:
        """Execute the tool deterministically with validated parameters."""
        ...

    async def run(self, raw_params: dict[str, Any] | TInput) -> TOutput:
        """Validate input dictionary, execute domain logic, and validate output."""
        if isinstance(raw_params, dict):
            validated_input = self.input_schema.model_validate(raw_params)
        else:
            validated_input = raw_params

        result = await self.execute(validated_input)

        # Enforce output schema validation
        if not isinstance(result, self.output_schema):
            return self.output_schema.model_validate(result)
        return result

    def to_mcp_tool_definition(self) -> dict[str, Any]:
        """Export tool declaration conforming to the Model Context Protocol (MCP) standard."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema.model_json_schema(),
        }
