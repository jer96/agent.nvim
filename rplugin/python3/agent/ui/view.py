import logging
from queue import Empty, Queue
from threading import Thread
from typing import Dict, List, Tuple

import pynvim

from ..llm.types import Message, TextContent
from .events import ToolContent, UIEvent, UIEventType
from .format import MessageFormatter

logger = logging.getLogger(__name__)


class ChatView:
    def __init__(self, nvim: pynvim.Nvim, event_queue: Queue):
        self.nvim = nvim
        self.chat_win = None
        self.chat_buf = None
        self.input_win = None
        self.input_buf = None
        self.formatter = MessageFormatter()
        self.event_queue = event_queue
        self.stream_start_line = None
        self.stream_end_line = None
        self.stream_end_line = None
        self.stream_text = ""
        self.message_marks = {}
        self.mark_namespace = None
        self.tool_statuses = {}

    @property
    def is_valid(self) -> bool:
        """Check if the chat windows and buffers are valid"""
        return self.chat_win and self.chat_win.valid and self.chat_buf and self.chat_buf.valid

    def create(self):
        """Initialize the chat interface UI components"""
        self._create_chat_buffers()
        self._create_chat_windows()
        self._show_chat_windows()
        self.mark_namespace = self.nvim.api.create_namespace("agent-chat")

    def _set_chat_buf_keymaps(self):
        opts = {"noremap": True, "silent": True}
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "<leader>]]", ":lua vim.fn.AgentNextMessage()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "<leader>[[", ":lua vim.fn.AgentPrevMessage()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "]t", ":lua vim.fn.AgentNextTool()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "[t", ":lua vim.fn.AgentPrevTool()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "<CR>", ":lua vim.fn.AgentSendStream()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "i", "<C-s>", "<Esc>:lua vim.fn.AgentSendStream()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "ss", "<Esc>:lua vim.fn.AgentSend()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "q", ":lua vim.fn.AgentClose()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "<C-x>", ":lua vim.fn.AgentClean()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "<C-n>", ":lua vim.fn.AgentStartConversation()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "q", ":lua vim.fn.AgentClose()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "<C-x>", ":lua vim.fn.AgentClean()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "<C-n>", ":lua vim.fn.AgentStartConversation()<CR>", opts)

    def _create_chat_buffers(self):
        self.chat_buf = self.nvim.api.create_buf(False, True)
        self.chat_buf.name = "agent chat"
        self.chat_buf.options["buftype"] = "nofile"
        self.chat_buf.options["modifiable"] = False
        self.chat_buf.options["filetype"] = "markdown"
        self.chat_buf.options["foldmethod"] = "marker"
        self.chat_buf.options["foldenable"] = True

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
        window_width = self.nvim.api.win_get_width(self.chat_win)
        self.formatter.window_width = window_width

        self.nvim.command("split")
        self.nvim.command("resize 5")
        self.input_win = self.nvim.current.window
        self.nvim.current.buffer = self.input_buf

    def _show_chat_windows(self):
        # Chat window specific configuration
        chat_win_config = {
            "number": False,
            "relativenumber": False,
            "wrap": True,
            "signcolumn": "yes",
            "foldmethod": "marker",
            "foldcolumn": "1",
            "foldenable": True,
        }

        input_win_config = {
            "winfixheight": True,
            "signcolumn": "no",
            "number": False,
            "relativenumber": False,
        }

        # Apply chat window configuration
        for option, value in chat_win_config.items():
            self.chat_win.options[option] = value

        # Apply input window configuration
        for option, value in input_win_config.items():
            self.input_win.options[option] = value

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

    def _update_buffer(self, lines: List[str], start: int, end: int):
        """Helper to update buffer content while preserving state"""
        self.chat_buf.options["modifiable"] = True
        self.nvim.api.buf_set_lines(self.chat_buf, start, end, False, lines)
        self.chat_buf.options["modifiable"] = False

    def _process_messages(self, messages: List[Message], start_idx: int, end_idx: int, window_width: int) -> List[str]:
        """Process a range of messages and return their formatted lines."""
        lines = []
        for i in range(start_idx, end_idx):
            message = messages[i]
            self.formatter.window_width = window_width
            message_lines, _ = self.formatter.format_message(message)
            lines.extend(message_lines)
        return lines

    def get_input_contents(self) -> str | None:
        """Get the contents of the input buffer"""
        if not self.input_buf or not self.input_buf.valid:
            return None

        lines = self.input_buf[:]
        message = "\n".join(lines)
        return message.strip()

    def clear_input(self):
        """Clear the input buffer"""
        if self.input_buf and self.input_buf.valid:
            self.input_buf[:] = [""]

    def focus_chat_window(self):
        """Focus the chat window"""
        self.nvim.current.window = self.chat_win

    def refresh_buffers(self):
        """Empty both chat and input buffers and reset processing state."""
        if self.chat_buf and self.chat_buf.valid:
            self._update_buffer([], 0, len(self.chat_buf))

        if self.input_buf and self.input_buf.valid:
            self.clear_input()

        self.stream_start_line = None

    def resize_windows(self):
        if not self.is_valid:
            return

        current_win = self.nvim.current.window
        self.nvim.current.window = self.input_win
        self.nvim.command("resize 5")
        self.nvim.current.window = current_win

    def start(self):
        """Start the event processing loop in a separate thread"""
        self.running = True

        def event_loop():
            while self.running:
                try:
                    event = self.event_queue.get(timeout=0.1)
                    self.nvim.async_call(self._handle_event, event)
                except Empty:
                    continue
                except Exception as e:
                    self.nvim.async_call(self.nvim.err_write, f"Event processing error: {str(e)}\n")

        self.event_thread = Thread(target=event_loop, daemon=True)
        self.event_thread.start()

    def _handle_messages_event(self, messages: List[Message]) -> None:
        """Handle a complete message event."""
        if not messages:
            return

        window_width = self.nvim.api.win_get_width(self.chat_win)
        start_line = len(self.chat_buf)

        for message in messages:
            self.formatter.window_width = window_width
            elements = self.formatter.format_message(message, start_line)
            for element in elements:
                if element.lines:
                    self._update_buffer(element.lines, start_line, start_line)
                if element.marks:
                    for mark in element.marks:
                        self._set_extmark(
                            mark.start_line,
                            mark.end_line,
                            mark.mark_type,
                            mark.mark_role,
                            mark.sign_text,
                        )
                start_line += len(element.lines)

        self._move_chat_cursor()

    def _handle_formatted_content(self, content) -> None:
        """Handle formatted content from a tool call or result."""
        current_line = len(self.chat_buf)

        elements = self.formatter.format_content(content, current_line)
        for element in elements:
            if element.lines:
                # Update buffer with the element's lines
                self._update_buffer(element.lines, current_line, current_line)

            if element.marks:
                for mark in element.marks:
                    self._set_extmark(
                        mark.start_line,
                        mark.end_line,
                        mark.mark_type,
                        mark.mark_role,
                        mark.sign_text,
                    )

        self._move_chat_cursor()

    def _handle_tool_batch_event(self, tool_batch: list[ToolContent]) -> None:
        """Handle a batched tool call and results event."""
        start_line = len(self.chat_buf)

        for tool in tool_batch:
            elements = self.formatter.format_content(tool, start_line)
            for element in elements:
                current_line = start_line
                if element.lines:
                    # Update buffer with the element's lines
                    self._update_buffer(element.lines, current_line, current_line)

                if element.marks:
                    for mark in element.marks:
                        self._set_extmark(
                            mark.start_line,
                            mark.end_line,
                            mark.mark_type,
                            mark.mark_role,
                            mark.sign_text,
                        )

                start_line += len(element.lines)

    def _handle_stream_start(self) -> None:
        """Handle the start of a streaming message."""
        self.nvim.command("RenderMarkdown disable")
        current_line_count = len(self.chat_buf)
        elements = self.formatter.format_message(
            Message(role="assistant", content=[TextContent(text="")]), current_line_count
        )
        header_element = elements[0]
        if header_element.lines:
            self._update_buffer(header_element.lines, current_line_count, current_line_count)
        if header_element.marks:
            for mark in header_element.marks:
                self._set_extmark(
                    mark.start_line,
                    mark.end_line,
                    mark.mark_type,
                    mark.mark_role,
                    mark.sign_text,
                )
        current_line_count = len(self.chat_buf)
        self.stream_start_line = current_line_count
        self.stream_end_line = current_line_count

    def _handle_stream_event(self, text: str) -> None:
        """Handle a streaming message event."""
        if not text or not self.is_valid:
            return
        logger.debug(f"stream event: {text}")

        try:
            # Update stream content and format using the formatter
            self.stream_text += text
            self.stream_start_line = 0 if self.stream_start_line is None else self.stream_start_line
            elements = self.formatter.format_stream_content(self.stream_text, self.stream_start_line)

            # Update buffer content
            if self.stream_start_line is not None and elements:
                # For now we expect only one element for streaming
                element = elements[0]
                self._update_buffer(element.lines, self.stream_start_line, self.stream_end_line)
                self.stream_end_line = self.stream_start_line + len(element.lines)
                self._move_chat_cursor()
        except Exception:
            logger.exception("Error in stream content handler")

    def _handle_stream_stop(self) -> None:
        """Handle the end of a streaming message."""
        # Re-enable markdown rendering first
        self.nvim.command("RenderMarkdown enable")

        # Reset streaming state
        self.stream_start_line = None
        self.stream_end_line = None
        self.stream_text = ""

        # Update cursor
        self._move_chat_cursor()

    def _handle_lines(self, lines: list[str]):
        current_line_count = len(self.chat_buf)
        self._update_buffer(lines, current_line_count, current_line_count)
        self._move_chat_cursor()

    def _move_chat_cursor(self, pos: tuple[int, int] = None):
        """Update the cursor position"""
        self.chat_win.cursor = pos or (len(self.chat_buf), 0)

    def _set_extmark(self, start_line: int, end_line: int, mark_type: str, mark_role: str, sign_text: str) -> int:
        """Create an extmark with consistent formatting."""
        sign_hl_group = f"{mark_type.title()}{mark_role.title()}"
        options = {"end_line": end_line, "sign_text": sign_text, "sign_hl_group": sign_hl_group, "priority": 100}

        mark_id = self.nvim.api.buf_set_extmark(self.chat_buf, self.mark_namespace, start_line, 0, options)

        self.message_marks[mark_id] = {
            "type": mark_type,
            "role": mark_role,
            "start": start_line,
            "end": start_line - 1,
            "options": options,
        }
        return mark_id

    def _handle_event(self, event: UIEvent) -> None:
        """Handle incoming UI events."""
        logger.debug(f"handling: {event.type}")
        try:
            event_handlers = {
                UIEventType.MESSAGES_EVENT: lambda: self._handle_messages_event(event.messages),
                UIEventType.MESSAGE_STREAM_START: self._handle_stream_start,
                UIEventType.MESSAGE_STREAM_EVENT: lambda: self._handle_stream_event(event.text),
                UIEventType.MESSAGE_STREAM_STOP: self._handle_stream_stop,
                UIEventType.TOOL_CALL: lambda: self._handle_formatted_content(event.tool_call),
                UIEventType.TOOL_RESULT: lambda: self._handle_formatted_content(event.tool_result),
                UIEventType.TOOL_BATCH: lambda: self._handle_tool_batch_event(event.tool_batch),
                UIEventType.CLEAR_INPUT: self.clear_input,
                UIEventType.CLOSE: self.close,
                UIEventType.DELETE_BUFFERS: self.delete_buffers,
                UIEventType.REFRESH_BUFFERS: self.refresh_buffers,
                UIEventType.SHOW: self.show,
                UIEventType.RESIZE: self.resize_windows,
                UIEventType.FOCUS_CHAT: self.focus_chat_window,
            }
            handler = event_handlers.get(event.type)
            if handler:
                handler()

        except Exception:
            logger.exception("Error handling event")

    def navigate_to_mark(self, mark_id: int) -> None:
        """Navigate to a specific extmark"""
        if mark_id in self.message_marks:
            mark = self.message_marks[mark_id]
            self.nvim.current.window = self.chat_win
            self.nvim.current.window.cursor = (mark["start"] + 1, 0)

    def _find_marks_by_type(self, mark_type: str) -> List[Tuple[int, Dict]]:
        """Find all marks of a specific type"""
        return [(id, mark) for id, mark in self.message_marks.items() if mark["type"] == mark_type]

    def _find_nearest_mark(self, line: int, marks: List[Tuple[int, Dict]], forward: bool = True) -> int | None:
        """Find the nearest mark to the current line"""
        if not marks:
            return None

        current_marks = sorted(marks, key=lambda x: x[1]["start"])
        if forward:
            for mark_id, mark in current_marks:
                if mark["start"] > line:
                    return mark_id
            return current_marks[0][0]  # Wrap around to first
        else:
            for mark_id, mark in reversed(current_marks):
                if mark["start"] < line:
                    return mark_id
            return current_marks[-1][0]  # Wrap around to last

    def navigate_messages(self, forward: bool = True) -> None:
        """Navigate between messages"""
        current_line = self.nvim.current.window.cursor[0] - 1
        message_marks = self._find_marks_by_type("message")
        mark_id = self._find_nearest_mark(current_line, message_marks, forward)
        if mark_id is not None:
            self.navigate_to_mark(mark_id)

    def navigate_tools(self, forward: bool = True) -> None:
        """Navigate between tool calls/results"""
        current_line = self.nvim.current.window.cursor[0] - 1
        tool_marks = self._find_marks_by_type("tool")
        mark_id = self._find_nearest_mark(current_line, tool_marks, forward)
        if mark_id is not None:
            self.navigate_to_mark(mark_id)

    def cleanup(self):
        """Cleanup resources when the plugin is unloaded"""
        self.running = False
        if hasattr(self, "event_thread"):
            self.event_thread.join(timeout=1.0)
        self.close()
        self.delete_buffers()
