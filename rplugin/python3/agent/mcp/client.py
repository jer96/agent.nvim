import asyncio
import logging
from contextlib import AsyncExitStack
from typing import List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..llm.providers.anthropic import AnthropicProvider
from ..llm.types import TextToolResult, Tool, ToolCall

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, server_params: List[StdioServerParameters], event_loop: asyncio.AbstractEventLoop):
        self.server_params_list = server_params
        self.sessions = {}  # server_id -> session
        self.tool_to_server = {}  # tool_name -> server_id
        self.exit_stack = AsyncExitStack()
        self.anthropic = AnthropicProvider()
        self.event_loop = event_loop

    def stop(self):
        async def cleanup_mcp():
            try:
                await self.cleanup()
            except Exception as e:
                self.nvim.err_write(f"Error cleaning up MCP client: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(cleanup_mcp(), self.event_loop)

    def start(self):
        async def initialize_mcp():
            try:
                await self.connect_to_servers()
            except Exception as e:
                self.nvim.err_write(f"Error initializing MCP client: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(initialize_mcp(), self.event_loop)

    async def _connect_to_server(self, server_id: str, params: StdioServerParameters):
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
        stdio, write = stdio_transport
        session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

        await session.initialize()
        self.sessions[server_id] = session

        # Update tool to server mapping
        tools = await session.list_tools()
        for tool in tools.tools:
            self.tool_to_server[tool.name] = server_id

        logger.debug(f"Connected to MCP server: {server_id}")
        return session

    async def connect_to_servers(self):
        """Connect to all servers provided in constructor"""
        for i, params in enumerate(self.server_params_list):
            server_id = f"server_{i}"
            await self._connect_to_server(server_id, params)

    async def get_session_info(self):
        """Get comprehensive information about all sessions"""
        all_sessions_info = {}

        for server_id, session in self.sessions.items():
            try:
                tools_response = await session.list_tools()
                prompts_response = await session.list_prompts()
                resources_response = await session.list_resources()

                session_info = {
                    "tools": [{"name": t.name, "description": t.description} for t in tools_response.tools],
                    "prompts": [{"name": p.name, "description": p.description} for p in prompts_response.prompts],
                    "resources": [{"name": r.name, "description": r.description} for r in resources_response.resources],
                }

                all_sessions_info[server_id] = session_info

            except Exception as e:
                logger.error(
                    f"Error getting session info for {
                        server_id}: {str(e)}"
                )
                all_sessions_info[server_id] = {"error": str(e)}

        return all_sessions_info

    async def get_available_tools(self) -> List[Tool]:
        """Get all tools from all servers"""
        all_tools = []
        for session in self.sessions.values():
            tools = await session.list_tools()
            all_tools.extend(
                [
                    Tool(name=tool.name, description=tool.description, input_schema=tool.inputSchema)
                    for tool in tools.tools
                ]
            )
        return all_tools

    async def call_tool(self, tool_call: ToolCall) -> List[TextToolResult]:
        # Find the correct server for this tool
        tool_name = tool_call.name
        tool_input = tool_call.input
        tool_id = tool_call.id
        server_id = self.tool_to_server.get(tool_name)
        if not server_id:
            logger.error(f"No server found for tool: {tool_name}")
            return []

        session = self.sessions[server_id]
        logger.debug(f"Calling tool {tool_name} on server {server_id}")
        result = await session.call_tool(tool_name, tool_input)

        tool_results = []
        for content in result.content:
            if content.type == "text":
                tool_results.append(TextToolResult(tool_use_id=tool_id, content=content.text, is_error=result.isError))
        return tool_results

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
