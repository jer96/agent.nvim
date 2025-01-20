import asyncio
import json
import logging
import uuid
from typing import List, Optional

import pynvim

from .context import AgentContext
from .llm.constants import (
    BASE_SYSTEM_PROMPT,
    FILE_CONTEXT_SYSTEM_PROMPT,
    create_file_prompt_from_buf,
    create_file_prompt_from_file,
)
from .llm.factory import LLMProviderFactory
from .mcp import MCPClient
from .storage import ConversationStorage

logger = logging.getLogger(__name__)


class ChatInterface:
    def __init__(self, nvim: pynvim.Nvim, context: AgentContext):
        self.nvim = nvim
        self.messages = []
        self.chat_win = None
        self.chat_buf = None
        self.input_win = None
        self.input_buf = None
        self.current_conversation_id = None
        self.mcp_client = None
        self.context = context
        self.is_active = False
        self.llm_provider = LLMProviderFactory.create(self.nvim)
        self.storage = ConversationStorage(self.nvim)
        self.start_mcp_client()

    def stop_mcp_client(self):
        async def cleanup_mcp():
            if self.mcp_client:
                await self.mcp_client.cleanup()
                self.mcp_client = None

        asyncio.run_coroutine_threadsafe(cleanup_mcp(), self.nvim.loop)

    def start_mcp_client(self):
        async def initialize_mcp():
            try:
                self.mcp_client = MCPClient()
                await self.mcp_client.connect_to_servers()
            except Exception as e:
                self.nvim.err_write(f"Error initializing MCP client: {str(e)}\n")

        asyncio.run_coroutine_threadsafe(initialize_mcp(), self.nvim.loop)

    def _start_new_conversation(self):
        """Start a new conversation with a unique ID and initial system prompt."""
        self.current_conversation_id = str(uuid.uuid4())
        self.messages = []

        # Add and store initial system prompt
        system_prompt = self._get_system_prompt_with_context()
        storage_messages = [{"role": "system", "content": system_prompt}]
        self.storage.save_conversation(self.current_conversation_id, storage_messages)

        logger.debug(
            f"Started new conversation with ID: {
                self.current_conversation_id}"
        )

    def _save_current_conversation(self):
        """Save the current conversation to storage."""
        if self.current_conversation_id and self.messages:
            self.storage.save_conversation(self.current_conversation_id, self.messages)

    def create_chat_panel(self):
        self._create_chat_buffers()
        self._create_chat_windows()
        self._show_chat_windows()

    def _set_chat_buf_keymaps(self):
        opts = {"noremap": True, "silent": True}
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "<CR>", ":lua vim.fn.AgentSendStream()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "i", "<C-s>", "<Esc>:lua vim.fn.AgentSendStream()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "ss", "<Esc>:lua vim.fn.AgentSend()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "q", ":lua vim.fn.AgentClose()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "<C-x>", ":lua vim.fn.AgentClean()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "q", ":lua vim.fn.AgentClose()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "<C-x>", ":lua vim.fn.AgentClean()<CR>", opts)

    def _create_chat_buffers(self):
        self.chat_buf = self.nvim.api.create_buf(False, True)
        self.chat_buf.name = "agent chat"
        self.chat_buf.options["buftype"] = "nofile"
        self.chat_buf.options["modifiable"] = False
        self.chat_buf.options["filetype"] = "markdown"

        self.input_buf = self.nvim.api.create_buf(False, True)
        self.input_buf.options["buftype"] = "nofile"
        self.input_buf.options["modifiable"] = True
        self.input_buf.options["filetype"] = "agent.nvim"
        self.input_buf.name = " "
        self._set_chat_buf_keymaps()

    def _create_chat_windows(self):
        # Create the vertical split for chat
        self.nvim.command("vsplit")
        self.chat_win = self.nvim.current.window
        self.nvim.current.buffer = self.chat_buf

        # Create input window as horizontal split
        self.nvim.command("split")
        self.nvim.command("resize 5")
        self.input_win = self.nvim.current.window
        self.nvim.current.buffer = self.input_buf

    def _show_chat_windows(self):
        # Set window options
        win_config = {
            "number": False,
            "relativenumber": False,
            "wrap": True,
            "signcolumn": "no",
        }

        for win in [self.chat_win, self.input_win]:
            for option, value in win_config.items():
                win.options[option] = value

        # Focus input window
        self.nvim.current.window = self.input_win
        self.nvim.command("startinsert")

    def show_chat(self):
        self.is_active = True
        # if windows are valid, reset view
        chat_win_valid = self.chat_win and self.chat_win.valid
        input_win_valid = self.input_win and self.input_win.valid
        if chat_win_valid and input_win_valid:
            self._show_chat_windows()
            return

        # if buffers are valid, create and show windows
        chat_buf_valid = self.chat_buf and self.chat_buf.valid
        input_buf_valid = self.input_buf and self.input_buf.valid
        if chat_buf_valid and input_buf_valid:
            self._create_chat_windows()
            self._show_chat_windows()
            return

        # else create everything new
        self.create_chat_panel()

    def close_chat(self):
        self.is_active = False
        if self.input_win and self.input_win.valid:
            self.nvim.api.win_close(self.input_win, True)
        if self.chat_win and self.chat_win.valid:
            self.nvim.api.win_close(self.chat_win, True)
        self.chat_win = None
        self.input_win = None

    def _delete_chat_buffers(self):
        if self.chat_buf and self.chat_buf.valid:
            self.nvim.api.buf_delete(self.chat_buf, {"force": True})
        if self.input_buf and self.input_buf.valid:
            self.nvim.api.buf_delete(self.input_buf, {"force": True})
        self.chat_buf = None
        self.input_buf = None

    def _update_chat_display(self):
        if not self.chat_buf or not self.chat_buf.valid:
            return

        window_width = self.nvim.api.win_get_width(self.chat_win)
        display_lines = [""]
        for msg in self.messages:

            def display_heading(role: str):
                heading_map = {"user": "#", "assistant": "##", "tool use": "###", "tool result": "###"}
                heading = heading_map.get(role, "#")
                role = role.upper()
                padding = " " * ((window_width - len(role) - len(heading)) // 2)
                role_header = f"{heading}{padding}{role}{padding}"

                if role in ["USER", "ASSISTANT"]:
                    display_lines.append("---")
                    display_lines.append(role_header)
                    display_lines.append("---")
                else:
                    display_lines.append(f"{heading} {role}")
                display_lines.append("")

            def display_wrapped_string(string: str):
                wrapped_content = string.split("\n")
                for line in wrapped_content:
                    display_lines.append(line)
                display_lines.append("")

            content = msg["content"]
            if isinstance(content, str):
                display_heading(msg["role"])
                display_wrapped_string(msg["content"])
            elif isinstance(content, list):
                for obj in content:
                    if obj.get("type", "") == "tool_use":
                        display_heading("tool use")
                        tool_name = obj.get("name", "")
                        tool_input = obj.get("input", {})
                        display_lines.append(f"Name: `{tool_name}`")
                        formatted_input = json.dumps(tool_input, indent=2)
                        display_lines.append("Input:")
                        display_lines.append("```")
                        display_lines.extend(formatted_input.splitlines())
                        display_lines.append("```")
                        display_lines.append("")
                    if obj.get("type", "") == "tool_result":
                        display_heading("tool result")
                        tool_content = obj.get("content", "")
                        is_error = obj.get("is_error", False)
                        display_lines.append(f"> Error: {is_error}")
                        display_lines.append("")
                        display_wrapped_string(tool_content)
                    elif obj.get("type", "") == "text":
                        text = obj.get("text", "")
                        display_heading(msg["role"])
                        display_wrapped_string(text)

        self.chat_buf.options["modifiable"] = True
        self.chat_buf[:] = display_lines
        self.chat_buf.options["modifiable"] = False

        # Scroll to bottom
        self.chat_win.cursor = (len(display_lines), 0)

    def _get_input_buf_contents(self) -> Optional[str]:
        if not self.input_buf or not self.input_buf.valid:
            return

        lines = self.input_buf[:]
        message = "\n".join(lines)
        return message.strip()

    def _get_system_prompt_with_context(self):
        """Get system prompt with current buffer and file contexts."""
        active_bufs = self.context.get_active_buffers()
        buf_contexts = [create_file_prompt_from_buf(buf) for buf in active_bufs]

        files = self.context.get_additional_files()
        file_contexts = [
            context for context in [create_file_prompt_from_file(file_path) for file_path in files] if context
        ]

        all_file_contexts = buf_contexts + file_contexts

        if not all_file_contexts:
            return BASE_SYSTEM_PROMPT

        files_content = "".join(all_file_contexts)
        return f"{BASE_SYSTEM_PROMPT} {FILE_CONTEXT_SYSTEM_PROMPT.replace("{{FILES}}", files_content)}"

    def send_message(self):
        if self.current_conversation_id is None:
            self._start_new_conversation()

        message = self._get_input_buf_contents()
        if message and message.strip():
            self.input_buf[:] = [""]
            self._add_message("user", message)
        system_prompt = self._get_system_prompt_with_context()

        async def mcp_send():
            available_tools = await self.mcp_client.get_available_tools()
            response_content = self.llm_provider.complete(
                messages=self.messages, tools=available_tools, system_prompt=system_prompt
            )

            tool_results = []
            assistant_content = []
            for content in response_content:
                if content.type == "text":
                    assistant_content.append({"type": "text", "text": content.text})
                elif content.type == "tool_use":
                    tool_name = content.name
                    tool_input = content.input
                    tool_id = content.id
                    assistant_content.append(
                        {"type": "tool_use", "id": tool_id, "name": tool_name, "input": tool_input}
                    )
                    results = await self.mcp_client.call_tool(tool_name, tool_id, tool_input)
                    tool_results.append(*results)

            return (assistant_content, tool_results)

        def mcp_send_on_complete(future):
            try:
                result = future.result()
                if result:
                    (assistant_content, tool_results) = result
                    logger.debug(f"mcp_send response {assistant_content}")
                    logger.debug(f"mcp_send tool result {tool_results}")
                    messages = [
                        {"role": "assistant", "content": assistant_content},
                        {"role": "user", "content": tool_results},
                    ]
                    if tool_results:
                        self.nvim.async_call(
                            lambda: [self._add_messages(messages), self._focus_chat_window(), self.send_message()]
                        )
                    else:
                        self.nvim.async_call(lambda: [self._add_messages(messages), self._focus_chat_window()])
            except Exception as e:
                logger.error(f"Error in message processing: {e}")

        future = asyncio.run_coroutine_threadsafe(mcp_send(), self.nvim.loop)
        future.add_done_callback(mcp_send_on_complete)

    def _add_messages(self, messages: List[dict]):
        for message in messages:
            if "content" in message and len(message.get("content", [])) == 0:
                continue
            self.messages.append(message)
        self._save_current_conversation()
        self._update_chat_display()

    def _add_message(self, role: str, content: str):
        """Add a message and save the conversation."""
        self.messages.append({"role": role, "content": content})
        self._save_current_conversation()
        self._update_chat_display()

    def _focus_chat_window(self):
        self.nvim.command("RenderMarkdown enable")
        self.nvim.current.window = self.chat_win

    def send_message_stream(self):
        if self.current_conversation_id is None:
            self._start_new_conversation()

        message = self._get_input_buf_contents()
        if not message:
            return

        self.input_buf[:] = [""]
        self.nvim.command("RenderMarkdown disable")

        # Get system prompt
        system_prompt = self._get_system_prompt_with_context()

        # Add user message to display messages
        self._add_message("user", message)

        # Get response using display messages but excluding system messages
        display_messages = [msg for msg in self.messages if msg["role"] != "system"]
        event_stream = self.llm_provider.complete_stream(messages=display_messages, system_prompt=system_prompt)

        assistant_content = ""
        for event in event_stream:
            if self.messages[-1].get("role", "") == "user":
                self.messages.append({"role": "assistant", "content": ""})

            assistant_content += event
            self.messages[-1]["content"] = assistant_content
            if self.chat_buf and self.chat_buf.valid and self.chat_win and self.chat_win.valid:
                self._update_chat_display()

        # Save the complete conversation
        if self.current_conversation_id:
            storage_messages = [{"role": "system", "content": system_prompt}] + self.messages
            self.storage.save_conversation(self.current_conversation_id, storage_messages)

        self._focus_chat_window()

    def load_conversation(self, conversation_id: str):
        """Load a specific conversation."""
        messages = self.storage.load_conversation(conversation_id)
        if messages:
            # Filter out system messages when loading
            self.messages = [msg for msg in messages if msg["role"] != "system"]
            self.current_conversation_id = conversation_id

            # Make sure chat interface is visible
            self.show_chat()

            # Update the display after ensuring windows are created
            if self.chat_buf and self.chat_buf.valid and self.chat_win and self.chat_win.valid:
                self._update_chat_display()
            return True
        return False

    def clean_chat(self):
        self.close_chat()
        self._delete_chat_buffers()
        self.messages = []
        self._start_new_conversation()
