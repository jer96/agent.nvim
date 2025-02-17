from queue import Empty, Queue
from threading import Thread
from typing import List

import pynvim

from ..llm.types import Message
from .events import UIEvent, UIEventType
from .format import MessageFormatter


class ChatView:
    def __init__(self, nvim: pynvim.Nvim, event_queue: Queue):
        self.nvim = nvim
        self.chat_win = None
        self.chat_buf = None
        self.input_win = None
        self.input_buf = None
        self.last_processed_index = -1
        self.formatter = MessageFormatter()
        self.event_queue = event_queue
        self.stream_start_line = None
        self.stream_message_index = None

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
        self.last_processed_index = -1

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

    def _handle_streaming_message(self, messages: List[Message], window_width: int):
        """Handle message updates in streaming mode."""
        message_index = len(messages) - 1

        # Handle any unprocessed messages before the streaming message
        if self.last_processed_index < message_index - 1:
            current_line_count = len(self.chat_buf)
            intermediate_lines = self._process_messages(
                messages, self.last_processed_index + 1, message_index, window_width
            )
            if intermediate_lines:
                self._update_buffer(intermediate_lines, current_line_count, current_line_count)
                self.stream_start_line = len(self.chat_buf)

        # Handle the streaming message
        last_message = messages[message_index]
        display_lines = self._format_message(last_message, window_width)

        if message_index != self.stream_message_index:
            # First time seeing this message, append it
            current_line_count = len(self.chat_buf)
            self._update_buffer(display_lines, current_line_count, current_line_count)
            self.stream_start_line = current_line_count
            self.stream_message_index = message_index
            self.last_processed_index = message_index
        else:
            # Update existing message in place
            if self.stream_start_line is not None:
                self._update_buffer(display_lines, self.stream_start_line, len(self.chat_buf))

        self._toggle_markdown_rendering(False)

    def _handle_normal_update(self, messages: List[Message], window_width: int):
        """Handle message updates in normal (non-streaming) mode."""
        current_line_count = len(self.chat_buf)
        new_lines = self._process_messages(messages, self.last_processed_index + 1, len(messages), window_width)

        if new_lines:
            self._update_buffer(new_lines, current_line_count, current_line_count)
            self.last_processed_index = len(messages) - 1
            self._toggle_markdown_rendering(True)

    def update_display(self, messages: List[Message], is_stream: bool = False):
        """Update the chat display with the given messages"""
        if not self.is_valid:
            return

        try:
            window_width = self.nvim.api.win_get_width(self.chat_win)

            if is_stream:
                self._handle_streaming_message(messages, window_width)
            else:
                self._handle_normal_update(messages, window_width)

            self.chat_win.cursor = (len(self.chat_buf), 0)

        except Exception as e:
            self.nvim.err_write(f"agent.nvim display update failed: {str(e)}\n")

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
        self._toggle_markdown_rendering(True)
        self.nvim.current.window = self.chat_win

    def _toggle_markdown_rendering(self, enable: bool):
        """Toggle markdown rendering in the chat buffer."""
        command = "enable" if enable else "disable"
        self.nvim.command(f"RenderMarkdown {command}")

    def refresh_buffers(self):
        """Empty both chat and input buffers and reset processing state."""
        if self.chat_buf and self.chat_buf.valid:
            self._update_buffer([], 0, len(self.chat_buf))

        if self.input_buf and self.input_buf.valid:
            self.clear_input()

        self.last_processed_index = -1
        self.stream_start_line = None
        self.stream_message_index = None

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

    def _handle_event(self, event: UIEvent):
        """Handle incoming UI events"""
        try:
            if event.type == UIEventType.UPDATE_MESSAGES:
                if event.messages:
                    self.update_display(event.messages, event.is_stream)
            elif event.type == UIEventType.CLEAR_INPUT:
                self.clear_input()
            elif event.type == UIEventType.CLOSE:
                self.close()
            elif event.type == UIEventType.DELETE_BUFFERS:
                self.delete_buffers()
            elif event.type == UIEventType.REFRESH_BUFFERS:
                self.refresh_buffers()
            elif event.type == UIEventType.SHOW:
                self.show()
            elif event.type == UIEventType.RESIZE:
                self.resize_windows()
            elif event.type == UIEventType.FOCUS_CHAT:
                self.focus_chat_window()
        except Exception as e:
            self.nvim.err_write(
                f"Error handling event {
                    event.type}: {str(e)}\n"
            )

    def cleanup(self):
        """Cleanup resources when the plugin is unloaded"""
        self.running = False
        if hasattr(self, "event_thread"):
            self.event_thread.join(timeout=1.0)
        self.close()
        self.delete_buffers()
