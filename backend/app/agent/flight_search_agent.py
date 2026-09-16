"""Central Flight Search Agent orchestrating tool discovery, selection, execution, and grounded response generation."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from app.agent.mcp_client import FlightSearchMCPClient
from app.agent.planner import FlightSearchPlanner, PlannedToolCall
from app.agent.prompts import FLIGHT_SEARCH_AGENT_SYSTEM_PROMPT
from app.agent.response_generator import FlightSearchResponseGenerator
from app.agent.state import AircraftReference, AirportReference, ConversationContext, ToolExecutionRecord
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentResponse(BaseModel):
    """Structured response object returned by the Flight Search Agent."""

    text: str = Field(description="Synthesized fact-grounded response text")
    tool_called: str = Field(description="Name of the MCP tool invoked")
    tool_arguments: Dict[str, Any] = Field(description="Validated parameters passed to the MCP tool")
    tool_result: Any = Field(description="Raw structured content returned by the MCP tool")
    conversation_id: str = Field(description="Active conversation context ID")
    referenced_aircraft: Optional[AircraftReference] = Field(
        default=None,
        description="Active aircraft reference updated in conversation memory",
    )
    referenced_airport: Optional[AirportReference] = Field(
        default=None,
        description="Active airport reference updated in conversation memory",
    )


class FlightSearchAgent:
    """Specialized AI agent dedicated exclusively to aviation information retrieval.

    Operates strictly via official aviation MCP tools, enforces zero-hallucination
    grounding rules, categorizes observed vs derived data, and maintains multi-turn
    conversational context for pronoun/follow-up resolution.
    """

    def __init__(
        self,
        mcp_client: FlightSearchMCPClient,
        system_prompt: str = FLIGHT_SEARCH_AGENT_SYSTEM_PROMPT,
    ) -> None:
        self.mcp_client = mcp_client
        self.system_prompt = system_prompt
        self.planner = FlightSearchPlanner()
        self.response_generator = FlightSearchResponseGenerator()
        self._conversations: Dict[str, ConversationContext] = {}

    def get_or_create_context(self, conversation_id: Optional[str] = None) -> ConversationContext:
        """Fetch or initialize a conversation context tracking multi-turn entities."""
        cid = conversation_id or str(uuid.uuid4())
        if cid not in self._conversations:
            self._conversations[cid] = ConversationContext(conversation_id=cid)
        return self._conversations[cid]

    async def ask(
        self,
        user_query: str,
        conversation_id: Optional[str] = None,
    ) -> AgentResponse:
        """Process a user inquiry through the full agent retrieval loop.

        Steps:
            1. Resolve conversational context and pronouns against active entities.
            2. Discover available MCP tools.
            3. Plan optimal MCP tool selection and parameter mapping.
            4. Execute tool via MCP client with parameter validation.
            5. Validate result and handle missing/unavailable data.
            6. Generate fact-grounded response distinguishing observed vs derived data.
            7. Update conversation memory and active entity references.

        Args:
            user_query: The natural language aviation question.
            conversation_id: Optional session identifier for multi-turn dialogues.

        Returns:
            AgentResponse containing the response text, tool records, and active state.
        """
        context = self.get_or_create_context(conversation_id)
        cid = context.conversation_id

        # 1. Tool discovery
        await self.mcp_client.discover_tools()

        # 2. Tool selection & query planning
        plan: PlannedToolCall = self.planner.plan(user_query, context)
        logger.info(
            "Agent planned tool '%s' for query '%s' (intent: %s)",
            plan.tool_name,
            user_query,
            plan.query_intent,
        )

        # 3. Structured tool execution via MCP client
        is_error = False
        try:
            tool_output = await self.mcp_client.call_tool(plan.tool_name, plan.arguments)
        except ToolError as te:
            is_error = True
            logger.warning("MCP tool execution error for '%s': %s", plan.tool_name, te)
            tool_output = {"error": str(te)}
        except Exception as exc:
            is_error = True
            logger.exception("Unexpected failure during MCP tool call")
            tool_output = {"error": f"Internal tool failure: {str(exc)}"}

        tool_record = ToolExecutionRecord(
            tool_name=plan.tool_name,
            arguments=plan.arguments,
            result=tool_output,
            is_error=is_error,
        )

        # 4. Result validation & response generation
        if is_error:
            response_text = (
                f"Unable to process query for tool '{plan.tool_name}': {tool_output.get('error')}. "
                "Please verify the aircraft identifier or coordinate boundaries."
            )
            ac_ref = None
            ap_ref = None
        else:
            response_text, ac_ref, ap_ref = self.response_generator.generate_response(
                user_query=user_query,
                plan=plan,
                tool_result=tool_output,
                context=context,
            )

        # 5. Update context memory
        context.add_turn(
            user_query=user_query,
            agent_response=response_text,
            tool_records=[tool_record],
            referenced_aircraft=ac_ref,
            referenced_airport=ap_ref,
        )

        return AgentResponse(
            text=response_text,
            tool_called=plan.tool_name,
            tool_arguments=plan.arguments,
            tool_result=tool_output,
            conversation_id=cid,
            referenced_aircraft=ac_ref or context.active_aircraft,
            referenced_airport=ap_ref or context.active_airport,
        )
