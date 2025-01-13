import asyncio
import logging
from datetime import datetime
from typing import Dict, List

import pynvim

from .chat import ChatInterface
from .context import AgentContext
from .mcp import MCPClient
from .util.logger import setup_logger

logger = logging.getLogger(__name__)


@pynvim.plugin
class AgentPlugin:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.context = AgentContext(nvim)
        self.chat_interface = ChatInterface(nvim, self.context)
        setup_logger()

    @pynvim.command("AgentDebug", nargs=0, sync=True)
    def debug_info(self):
        """Print debug information"""
        self.nvim.out_write(f"Plugin loaded at: {__file__}\n")

    @pynvim.command("AgentTest", nargs="*", range="")
    def testcommand(self, args, range):
        self.nvim.current.line = "Command with args: {}, range: {}".format(args, range)

    @pynvim.command("AgentToggle", sync=True)
    def toggle_chat(self):
        if self.chat_interface.is_active:
            self.chat_interface.close_chat()
        else:
            self.chat_interface.show_chat()

    @pynvim.function("AgentSend")
    def send_message(self, args: List[str]):
        self.chat_interface.send_message()

    @pynvim.function("AgentSendStream")
    def send_message_stream(self, args: List[str]):
        self.nvim.async_call(self.chat_interface.send_message_stream)

    @pynvim.function("AgentClose", sync=True)
    def close_chat(self, args: List[str]):
        self.chat_interface.close_chat()

    @pynvim.function("AgentClean", sync=True)
    def clean_chat(self, args: List[str]):
        self.chat_interface.clean_chat()

    @pynvim.command("AgentContext", sync=True)
    def show_context_picker(self):
        self.nvim.command('lua require("agent.ui.telescope").file_picker_with_context()')

    @pynvim.function("AgentContextGetData", sync=True)
    def get_context_data(self, args: List[str]) -> Dict:
        return self.context.get_context_data()

    @pynvim.function("AgentContextAddFile", sync=True)
    def add_file(self, args: List[str]):
        if args and len(args) > 0:
            self.context.add_file(args[0])

    @pynvim.function("AgentContextRemoveFile", sync=True)
    def remove_file(self, args: List[str]):
        if args and len(args) > 0:
            self.context.remove_file(args[0])

    @pynvim.function("AgentContextClearFiles", sync=True)
    def clear_files(self, args: List[str]):
        self.context.clear_additional_files()

    @pynvim.function("AgentContextClearBuffers", sync=True)
    def clear_buffers(self, args: List[str]):
        self.context.clear_active_buffers()

    @pynvim.function("AgentContextClearAll", sync=True)
    def clear_all(self, args: List[str]):
        self.context.clear_active_buffers()
        self.context.clear_additional_files()

    @pynvim.function("AgentContextToggleBuffer", sync=True)
    def toggle_buffer(self, args: List[str]):
        if args and len(args) > 0:
            self.context.toggle_buffer(int(args[0]))

    @pynvim.function("AgentListConversations", sync=True)
    def list_conversations(self, args) -> List[Dict]:
        conversations = self.chat_interface.storage.list_conversations()
        return [
            {
                "id": conv["id"],
                "timestamp": datetime.fromisoformat(conv["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                "message_count": conv["message_count"],
            }
            for conv in conversations
        ]

    @pynvim.command("AgentLoadConversation", nargs=1, sync=True)
    def load_conversation(self, args):
        try:
            conv_id = args[0]
            # Close the conversations list buffer if it exists
            for buf in self.nvim.api.list_bufs():
                if self.nvim.api.buf_get_name(buf).endswith("agent-conversations-list"):
                    # Find and close any window displaying this buffer
                    for win in self.nvim.api.list_wins():
                        if self.nvim.api.win_get_buf(win) == buf:
                            self.nvim.api.win_close(win, True)
                    # Delete the buffer
                    self.nvim.api.buf_delete(buf, {"force": True})
                    break

            if self.chat_interface.load_conversation(conv_id):
                self.nvim.out_write(f"Loaded conversation {conv_id}\n")
            else:
                self.nvim.err_write(f"Conversation {conv_id} not found\n")
        except Exception as e:
            self.nvim.err_write(f"Error loading conversation: {str(e)}\n")

    @pynvim.command("AgentMCPStart", sync=True)
    def start_mcp(self):
        """Start MCP client with given server script path"""

        async def initialize_mcp():
            try:
                self.mcp_client = MCPClient()
                await self.mcp_client.connect_to_server()
            except Exception as e:
                self.nvim.err_write(f"Error initializing MCP client: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(initialize_mcp(), self.nvim.loop)

    @pynvim.command("AgentMCPStop", sync=True)
    def stop_mcp(self):
        """Stop MCP client and cleanup"""

        async def cleanup_mcp():
            if self.mcp_client:
                await self.mcp_client.cleanup()
                self.mcp_client = None

        asyncio.run_coroutine_threadsafe(cleanup_mcp(), self.nvim.loop)

    @pynvim.command("AgentMCPTest", sync=True)
    def test_mcp(self):
        """Test MCP connection and available tools"""
        if not self.mcp_client or not self.mcp_client.session:
            logger.debug("MCP client not connected. Run :AgentMCPStart first")
            return

        async def run_test():
            try:
                logger.debug("-- run test start --")
                # Get session
                session = self.mcp_client.session

                # List available prompts
                prompts = await session.list_prompts()
                logger.debug(prompts)

                # Get a prompt
                prompt = await session.get_prompt("echo_prompt", arguments={"message": "hey"})
                logger.debug(prompt)

                # List available resources
                resources = await session.list_resources()
                logger.debug(resources)

                # List available tools
                tools = await session.list_tools()
                logger.debug(tools)

                # Read a resource
                resource = await session.read_resource("echo://hey")
                logger.debug(resource)

                # List available tools
                tools_response = await session.list_tools()
                logger.debug("Available tools:")
                for tool in tools_response.tools:
                    logger.debug(f"- {tool.name}: {tool.description}")

                # Try calling echo_tool if available
                if any(tool.name == "echo_tool" for tool in tools_response.tools):
                    result = await session.call_tool("echo_tool", {"message": "MCP test successful!"})
                    logger.debug(f"Test tool call result: {result.content}")

                logger.debug("-- run test end --")
            except Exception as e:
                logger.error(f"MCP test error: {str(e)}")

        asyncio.run_coroutine_threadsafe(run_test(), self.nvim.loop)
