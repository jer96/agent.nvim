import logging
from queue import Empty, Queue
from threading import Thread
from typing import List

import pynvim

from ..llm.types import Message
from .events import UIEvent, UIEventType
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

    @property
    def is_valid(self) -> bool:
        """Check if the chat windows and buffers are valid"""
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
        win_config = {
            "number": False,
            "relativenumber": False,
            "wrap": True,
            "signcolumn": "no",
        }

        input_win_config = {
            "winfixheight": True,
        }

        for win in [self.chat_win, self.input_win]:
            for option, value in win_config.items():
                win.options[option] = value

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

    def _format_message(self, message: Message, window_width: int) -> List[str]:
        """Format a single message into displayable lines using MessageFormatter."""
        self.formatter.window_width = window_width
        return self.formatter.format_message(message)

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
            message_lines = self._format_message(message, window_width)
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
        current_line_count = len(self.chat_buf)

        for message in messages:
            lines = self._format_message(message, window_width)
            if lines:
                # Follow the same pattern as _handle_lines
                if current_line_count > 0:
                    lines.insert(0, "")
                self._update_buffer(lines, current_line_count, current_line_count)
                current_line_count = len(self.chat_buf)

        self._move_chat_cursor()

    def _handle_stream_start(self) -> None:
        """Handle the start of a streaming message."""
        current_line_count = len(self.chat_buf)
        self.stream_start_line = current_line_count
        self.stream_end_line = current_line_count
        self.stream_text = ""
        self.nvim.command('RenderMarkdown disable')

    def _handle_stream_stop(self) -> None:
        """Handle the end of a streaming message."""
        # Re-enable markdown rendering first
        self.nvim.command('RenderMarkdown enable')

        # Reset streaming state
        self.stream_start_line = None
        self.stream_end_line = None
        self.stream_text = ""

        # Update cursor
        self._move_chat_cursor()

    def _handle_stream_event(self, text: str) -> None:
        """Handle a streaming message event."""
        if not text or not self.is_valid:
            return
        logger.debug(f"strem event: {text}")

        try:
            # Update stream content and format using the formatter
            self.stream_text += text
            window_width = self.nvim.api.win_get_width(self.chat_win)
            new_lines = self.formatter.format_stream_content(self.stream_text, window_width)

            # Update buffer content
            if self.stream_start_line is not None:
                # Update the entire streaming message content
                self._update_buffer(new_lines, self.stream_start_line, self.stream_end_line)
                self.stream_end_line = self.stream_start_line + len(new_lines)
                self._move_chat_cursor()
        except Exception:
            logger.exception("Error in stream content handler")


    def _handle_tool_call_event(self, tool_call) -> None:
        """Handle a tool call event."""
        if self.stream_start_line is None:
            self._handle_stream_start()

        lines = self.formatter.format_content(tool_call)
        self._handle_lines(lines)

    def _handle_tool_result_event(self, tool_result) -> None:
        """Handle a tool result event."""
        lines = self.formatter.format_content(tool_result)
        self._handle_lines(lines)

    def _handle_tool_batch_event(self, tool_batch) -> None:
        """Handle a batched tool call and results event."""
        for tool in tool_batch:
            lines = self.formatter.format_content(tool)
            self._handle_lines(lines)


    def _handle_lines(self, lines: list[str]):
        current_line_count = len(self.chat_buf)
        self._update_buffer(lines, current_line_count, current_line_count)
        self._move_chat_cursor()

    def _move_chat_cursor(self, pos: tuple[int, int] = None):
        """Update the cursor position"""
        self.chat_win.cursor = pos or (len(self.chat_buf), 0)


    def _handle_event(self, event: UIEvent) -> None:
        """Handle incoming UI events."""
        logger.debug(f"handling: {event.type}")
        try:
            event_handlers = {
                UIEventType.MESSAGES_EVENT: lambda: self._handle_messages_event(event.messages),
                UIEventType.MESSAGE_STREAM_START: self._handle_stream_start,
                UIEventType.MESSAGE_STREAM_EVENT: lambda: self._handle_stream_event(event.text),
                UIEventType.MESSAGE_STREAM_STOP: self._handle_stream_stop,
                UIEventType.TOOL_CALL: lambda: self._handle_tool_call_event(event.tool_call),
                UIEventType.TOOL_RESULT: lambda: self._handle_tool_result_event(event.tool_result),
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

    def cleanup(self):
        """Cleanup resources when the plugin is unloaded"""
        self.running = False
        if hasattr(self, "event_thread"):
            self.event_thread.join(timeout=1.0)
        self.close()
        self.delete_buffers()
