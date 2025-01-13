import logging
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

server_params = StdioServerParameters(
    command="python",  # Executable
    # Optional command line arguments
    args=["/Users/jeremiahbill/projects/mcp-test/server.py"],
    env=None,  # Optional environment variables
)


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self):
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
        logger.debug("Connected to MCP server")
        logger.debug("session info")
        session_info = await self.get_session_info()
        logger.debug(session_info)

        # List available tools
        # response = await self.session.list_tools()
        # tools = response.tools
        # logger.debug("Connected to server with tools: %s", [tool.name for tool in tools])
        return self.session

    async def get_session_info(self):
        """Get comprehensive information about the current session"""
        if not self.session:
            logger.debug("No active MCP session")
            return None

        try:
            tools_response = await self.session.list_tools()
            prompts_response = await self.session.list_prompts()
            resources_response = await self.session.list_resources()

            session_info = {
                "tools": [{"name": t.name, "description": t.description} for t in tools_response.tools],
                "prompts": [{"name": p.name, "description": p.description} for p in prompts_response.prompts],
                "resources": [{"name": r.name, "description": r.description} for r in resources_response.resources],
            }

            return session_info

        except Exception as e:
            logger.error(f"Error getting session info: {str(e)}")
            return None

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
