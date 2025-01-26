import asyncio
import logging
import uuid
from typing import List

import pynvim

from .context import AgentContext
from .llm.constants import SYSTEM_PROMPT, create_file_prompt_from_buf, create_file_prompt_from_file
from .llm.factory import LLMProviderFactory
from .llm.types import (
    CompletionResponse,
    InferenceConfig,
    Message,
    TextContent,
    ToolCall,
)
from .mcp import MCPClient, get_file_system_server_params
from .storage import ChatStorage
from .ui import ChatView

logger = logging.getLogger(__name__)


class ChatInterface:
    def __init__(self, nvim: pynvim.Nvim, context: AgentContext):
        self.nvim = nvim
        self.context = context
        self.is_active = False
        self.current_conversation_id: str | None = None
        self.messages: List[Message] = []
        self.llm_provider = LLMProviderFactory.create(self.nvim)
        self.view = ChatView(self.nvim)
        self.storage = ChatStorage(self.nvim)
        self.mcp_client = MCPClient(self._get_mcp_server_params(), self.nvim.loop)
        self.mcp_client.start()

    def show_chat(self):
        self.is_active = True
        self.view.show()

    def close_chat(self):
        self.is_active = False
        self.view.close()

    def clean_chat(self):
        self.close_chat()
        self.view.delete_buffers()
        self.messages = []
        self._start_new_conversation()

    def _get_mcp_server_params(self):
        file_system_server_params = get_file_system_server_params([self.context.cwd])
        return [file_system_server_params]

    def _start_new_conversation(self):
        self.current_conversation_id = str(uuid.uuid4())
        self._save_current_conversation()

    def _save_current_conversation(self):
        if self.current_conversation_id and self.messages:
            self.storage.save_conversation(self.current_conversation_id, self.messages)

    def load_conversation(self, conversation_id: str) -> bool:
        """Load a specific conversation."""
        loaded_messages = self.storage.load_conversation(conversation_id)
        if not loaded_messages:
            return False

        self.messages = loaded_messages
        self.current_conversation_id = conversation_id

        # Make sure chat interface is visible and updated
        self.is_active = True
        self.view.show()
        self.view.update_display(self.messages)
        self.view.focus_chat_window()

        return True

    def _get_system_prompt_with_context(self):
        """Get system prompt with current buffer and file contexts."""
        active_bufs = self.context.get_active_buffers()
        buf_contexts = [create_file_prompt_from_buf(buf) for buf in active_bufs]

        files = self.context.get_additional_files()
        file_contexts = [
            context for context in [create_file_prompt_from_file(file_path) for file_path in files] if context
        ]

        all_file_contexts = buf_contexts + file_contexts
        files_content = "".join(all_file_contexts) if all_file_contexts else ""

        return SYSTEM_PROMPT.replace("{{FILES}}", files_content).replace("{{CWD}}", self.context.cwd)

    def _add_messages(self, messages: List[Message]):
        """Add messages to the conversation and update display."""
        self.messages.extend(messages)
        self._save_current_conversation()
        self.view.update_display(self.messages)

    def send_message(self):
        if self.current_conversation_id is None:
            self._start_new_conversation()

        message = self.view.get_input_contents()
        if message and message.strip():
            self.view.clear_input()
            self._add_messages([Message(role="user", content=message)])
        system_prompt = self._get_system_prompt_with_context()

        async def mcp_send() -> List[Message]:
            tools = await self.mcp_client.get_available_tools()
            config = InferenceConfig(system_prompt=system_prompt)
            response: CompletionResponse = self.llm_provider.complete(
                messages=self.messages, tools=tools, config=config
            )

            tool_results = []
            assistant_content = []
            for content in response.content:
                if isinstance(content, TextContent):
                    assistant_content.append(content)
                elif isinstance(content, ToolCall):
                    assistant_content.append(content)
                    results = await self.mcp_client.call_tool(content)
                    tool_results.append(*results)

            logger.debug(f"mcp_send response {assistant_content}")
            logger.debug(f"mcp_send tool result {tool_results}")

            messages = []
            if assistant_content:
                messages.append(Message(role="assistant", content=assistant_content))
            if tool_results:
                messages.append(Message(role="user", content=tool_results))
            return messages

        def mcp_send_on_complete(future):
            try:
                messages = future.result()
                if messages:
                    if len(messages) > 1:
                        self.nvim.async_call(
                            lambda: [
                                self._add_messages(messages),
                                self.view.focus_chat_window(),
                                self.send_message(),
                            ]
                        )
                    else:
                        self.nvim.async_call(
                            lambda: [
                                self._add_messages(messages),
                                self.view.focus_chat_window(),
                            ]
                        )
            except Exception as e:
                logger.error(f"Error in message processing: {e}")

        future = asyncio.run_coroutine_threadsafe(mcp_send(), self.nvim.loop)
        future.add_done_callback(mcp_send_on_complete)

    def send_message_stream(self):
        if self.current_conversation_id is None:
            self._start_new_conversation()

        message = self.view.get_input_contents()
        if message and message.strip():
            self.view.clear_input()
            self._add_messages([Message(role="user", content=message)])

        system_prompt = self._get_system_prompt_with_context()
        config = InferenceConfig(system_prompt=system_prompt)
        event_stream = self.llm_provider.complete_stream(messages=self.messages, config=config)

        self.view.begin_streaming()
        assistant_message = Message(role="assistant", content="")
        for event in event_stream:
            if self.messages[-1].role == "user":
                self.messages.append(assistant_message)
            assistant_message.content = assistant_message.content + event
            self.view.update_display(self.messages)
        self._save_current_conversation()
        self.view.end_streaming()
