import asyncio
import logging
import uuid
from functools import partial
from typing import Any, Awaitable, Callable, List, TypeVar

import pynvim

from .context import AgentContext
from .llm.constants import ASSISTANT_READ_FILES_PROMPT
from .llm.factory import LLMProviderFactory
from .llm.types import (
    CompletionResponse,
    ContentType,
    FileContext,
    InferenceConfig,
    Message,
    TextContent,
    ToolCall,
    ToolResult,
)
from .mcp import MCPClient, get_file_system_server_params
from .storage import ChatStorage
from .tools import ToolRegistry
from .ui import ChatView

logger = logging.getLogger(__name__)


T = TypeVar("T")
LoopConditionFunc = Callable[[List[Message]], bool]


def last_message_contains_tool_use(messages: List[Message]) -> bool:
    if not messages:
        return False

    last_message = messages[-1]
    content = last_message.content
    if isinstance(content, list):
        has_tools = any(isinstance(item, (ToolResult)) for item in content)
    else:
        has_tools = isinstance(content, ToolResult)

    return has_tools


def default_loop_condition(messages: List[Message]) -> bool:
    """Default condition that determines if the agent should loop (i.e. process tool results)."""
    return last_message_contains_tool_use(messages)


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
        self.tool_registry = ToolRegistry(self.context)
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

    def start_conversation(self):
        self.view.refresh_buffers()
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

    async def _attach_context(self, context: FileContext):
        if last_message_contains_tool_use(self.messages):
            return

        context_tool_calls = context.get_read_file_tool_calls()
        if not context_tool_calls:
            return

        tool_results: ToolResult = []
        for tool_call in context_tool_calls:
            results = await self.mcp_client.call_tool(tool_call)
            tool_results.append(*results)

        assistant_content = [TextContent(text=ASSISTANT_READ_FILES_PROMPT), *context_tool_calls]
        last_user_message = self.messages.pop()
        self.messages.extend(
            [
                Message(role="user", content=context.get_prompt()),
                Message(role="assistant", content=assistant_content),
                Message(role="user", content=tool_results),
                last_user_message,
            ],
        )

    def _add_messages(self, messages: List[Message]):
        """Add messages to the conversation and update display."""
        self.messages.extend(messages)
        self._save_current_conversation()
        self.view.update_display(self.messages)

    def _finalize_messages(self, assistant_content: List[ContentType], tool_results=List[ToolResult]):
        messages = []
        if assistant_content:
            messages.append(Message(role="assistant", content=assistant_content))
        if tool_results:
            messages.append(Message(role="user", content=tool_results))
        return messages

    def _handle_user_input(self):
        if self.current_conversation_id is None:
            self._start_new_conversation()

        message = self.view.get_input_contents()
        if message:
            self.view.clear_input()
            self._add_messages([Message(role="user", content=message)])

    def _schedule_coroutine(
        self,
        coro: Callable[[], Awaitable[T]],
        done_callback: Callable[[asyncio.Future[T]], Any],
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(coro(), self.nvim.loop)
        future.add_done_callback(done_callback)

    def _mcp_send_on_complete(
        self,
        future: asyncio.Future[List[Message]],
        stream: bool = False,
        loop_conditions: List[LoopConditionFunc] | None = None,
    ) -> None:
        """Callback to process LLM response messages.

        asyncio callbacks cannot make blocking requests (including accessing state)
        therefore all stateful operations are wrapped in an nvim async_call

        https://pynvim.readthedocs.io/en/latest/api/nvim.html
        """
        messages: List[Message] = future.result()
        if not messages:
            return
        add_message_partial = partial(self._add_messages, messages=messages)
        handle_tools_partial = partial(self.tool_registry.handle_messages, messages=messages)
        funcs_to_call = [add_message_partial, handle_tools_partial]
        loop_conditions = loop_conditions or [default_loop_condition]
        should_loop = any(condition(messages) for condition in loop_conditions)
        if should_loop:
            send_func = self.send_message_stream if stream else self.send_message
            funcs_to_call.append(send_func)
        self.nvim.async_call(lambda: [f() for f in funcs_to_call])

    def send_message(self):
        self._handle_user_input()
        system_prompt = self.context.get_system_prompt_with_context()
        context = self.context.get_file_context()
        config = InferenceConfig(system_prompt=system_prompt)

        async def mcp_send() -> List[Message]:
            await self._attach_context(context)
            tools = await self.mcp_client.get_available_tools()
            response: CompletionResponse = await self.llm_provider.async_complete(
                messages=self.messages, tools=tools, config=config
            )
            tool_results, assistant_content = [], []
            for content in response.content:
                if isinstance(content, TextContent):
                    assistant_content.append(content)
                elif isinstance(content, ToolCall):
                    assistant_content.append(content)
                    results = await self.mcp_client.call_tool(content)
                    tool_results.append(*results)
            return self._finalize_messages(assistant_content, tool_results)

        done_callback = partial(self._mcp_send_on_complete, stream=False)
        self._schedule_coroutine(mcp_send, done_callback)

    def send_message_stream(self):
        self._handle_user_input()
        system_prompt = self.context.get_system_prompt_with_context()
        context = self.context.get_file_context()
        config = InferenceConfig(system_prompt=system_prompt)

        async def mcp_send_stream():
            await self._attach_context(context)
            tools = await self.mcp_client.get_available_tools()
            event_stream = self.llm_provider.async_complete_stream(messages=self.messages, tools=tools, config=config)
            tool_results, assistant_content = [], []
            assistant_message = Message(role="assistant", content="")
            self.nvim.async_call(self.view.begin_streaming)
            async for event in event_stream:
                if self.messages[-1].role == "user":
                    self.messages.append(assistant_message)
                if isinstance(event, TextContent):
                    assistant_message.content += event.text
                    self.nvim.async_call(self.view.update_display, self.messages)
                elif isinstance(event, ToolCall):
                    assistant_content.append(event)
                    results = await self.mcp_client.call_tool(event)
                    tool_results.append(*results)
            self.nvim.async_call(self.view.end_streaming)
            return self._finalize_messages(assistant_content, tool_results)

        done_callback = partial(self._mcp_send_on_complete, stream=True)
        self._schedule_coroutine(mcp_send_stream, done_callback)
