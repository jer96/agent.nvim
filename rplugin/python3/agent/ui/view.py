import json
from typing import Any, List

import pynvim

from ..llm.types import (
    Message,
    TextContent,
    ToolCall,
    ToolResult,
)


class ChatView:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.chat_win = None
        self.chat_buf = None
        self.input_win = None
        self.input_buf = None

    @property
    def is_valid(self) -> bool:
        """Update the chat display with streaming content"""
        return self.chat_win and self.chat_win.valid and self.chat_buf and self.chat_buf.valid

    def create(self):
        """Initialize the chat interface UI components"""
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
        self.nvim.command("vsplit")
        self.chat_win = self.nvim.current.window
        self.nvim.current.buffer = self.chat_buf

        self.nvim.command("split")
        self.nvim.command("resize 5")
        self.input_win = self.nvim.current.window
        self.nvim.current.buffer = self.input_buf

    def _show_chat_windows(self):
        win_config = {
            "number": False,
            "relativenumber": False,
            "wrap": True,
            "signcolumn": "no",
        }

        for win in [self.chat_win, self.input_win]:
            for option, value in win_config.items():
                win.options[option] = value

        self.nvim.current.window = self.input_win
        self.nvim.command("startinsert")

    def show(self):
        """Show or restore the chat interface"""
        chat_win_valid = self.chat_win and self.chat_win.valid
        input_win_valid = self.input_win and self.input_win.valid
        if chat_win_valid and input_win_valid:
            self._show_chat_windows()
            return

        chat_buf_valid = self.chat_buf and self.chat_buf.valid
        input_buf_valid = self.input_buf and self.input_buf.valid
        if chat_buf_valid and input_buf_valid:
            self._create_chat_windows()
            self._show_chat_windows()
            return

        self.create()

    def close(self):
        """Close the chat interface windows"""
        if self.input_win and self.input_win.valid:
            self.nvim.api.win_close(self.input_win, True)
        if self.chat_win and self.chat_win.valid:
            self.nvim.api.win_close(self.chat_win, True)
        self.chat_win = None
        self.input_win = None

    def delete_buffers(self):
        """Delete the chat interface buffers"""
        if self.chat_buf and self.chat_buf.valid:
            self.nvim.api.buf_delete(self.chat_buf, {"force": True})
        if self.input_buf and self.input_buf.valid:
            self.nvim.api.buf_delete(self.input_buf, {"force": True})
        self.chat_buf = None
        self.input_buf = None

    def update_display(self, messages: List[Message]):
        """Update the chat display with the given messages"""
        if not self.is_valid:
            return

        window_width = self.nvim.api.win_get_width(self.chat_win)
        display_lines = [""]
        for message in messages:
            role = message.role

            def display_heading():
                nonlocal role
                heading_map = {"user": "#", "assistant": "##"}
                heading = heading_map.get(role, "#")
                role = role.upper()
                padding = " " * ((window_width - len(role) - len(heading)) // 2)
                role_header = f"{heading}{padding}{role}{padding}"
                display_lines.append("---")
                display_lines.append(role_header)
                display_lines.append("---")
                display_lines.append("")

            def display_wrapped_string(string: str):
                wrapped_content = string.split("\n")
                for line in wrapped_content:
                    display_lines.append(line)
                display_lines.append("")

            def display_blocks(content: Any):
                if isinstance(content, str):
                    display_heading()
                    display_wrapped_string(content)
                elif isinstance(content, TextContent):
                    display_heading()
                    display_wrapped_string(content.text)
                elif isinstance(content, ToolCall):
                    display_lines.append("### TOOL CALL")
                    display_lines.append("")
                    tool_call = content
                    tool_name = tool_call.name
                    tool_input = tool_call.input
                    display_lines.append(f"Name: `{tool_name}`")
                    formatted_input = json.dumps(tool_input, indent=2)
                    display_lines.append("Input:")
                    display_lines.append("```")
                    display_lines.extend(formatted_input.splitlines())
                    display_lines.append("```")
                    display_lines.append("")
                elif isinstance(content, ToolResult):
                    display_lines.append("### TOOL RESULT")
                    display_lines.append("")
                    tool_result = content
                    tool_content = tool_result.content
                    is_error = tool_result.is_error
                    display_lines.append(f"> Error: {is_error}")
                    display_lines.append("")
                    display_wrapped_string(tool_content)
                elif isinstance(content, list):
                    for con in content:
                        display_blocks(con)

            display_blocks(message.content)

        self.chat_buf.options["modifiable"] = True
        self.chat_buf[:] = display_lines
        self.chat_buf.options["modifiable"] = False
        self.chat_win.cursor = (len(display_lines), 0)

    def get_input_contents(self) -> str | None:
        """Get the contents of the input buffer"""
        if not self.input_buf or not self.input_buf.valid:
            return

        lines = self.input_buf[:]
        message = "\n".join(lines)
        return message.strip()

    def clear_input(self):
        """Clear the input buffer"""
        if self.input_buf and self.input_buf.valid:
            self.input_buf[:] = [""]

    def focus_chat_window(self):
        """Focus the chat window"""
        self.nvim.command("RenderMarkdown enable")
        self.nvim.current.window = self.chat_win

    def toggle_markdown_rendering(self, enable: bool):
        """Toggle markdown rendering in the chat buffer."""
        command = "enable" if enable else "disable"
        self.nvim.command(f"RenderMarkdown {command}")

    def begin_streaming(self):
        self.toggle_markdown_rendering(False)

    def end_streaming(self):
        self.toggle_markdown_rendering(True)
        self.focus_chat_window()
