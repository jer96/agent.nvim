from typing import Optional

import pynvim

from .llm import LLMProvider


class ChatInterface:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.messages = []
        self.chat_win = None
        self.chat_buf = None
        self.input_win = None
        self.input_buf = None
        self.llm_provider = LLMProvider(nvim)

    def _set_chat_buf_keymaps(self):
        opts = {"noremap": True, "silent": True}
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "<CR>", ":lua vim.fn.AgentSendStream()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "i", "<C-s>", "<Esc>:lua vim.fn.AgentSendStream()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "ss", "<Esc>:lua vim.fn.AgentSend()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.input_buf, "n", "q", ":lua vim.fn.AgentClose()<CR>", opts)
        self.nvim.api.buf_set_keymap(self.chat_buf, "n", "q", ":lua vim.fn.AgentClose()<CR>", opts)

    def create_chat_window(self):
        # Create main chat buffer
        self.chat_buf = self.nvim.request("nvim_create_buf", False, True)
        self.chat_buf.name = "agent chat"
        self.chat_buf.options["buftype"] = "nofile"
        self.chat_buf.options["modifiable"] = False
        self.chat_buf.options["filetype"] = "markdown"

        # Create the vertical split for chat
        self.nvim.command("vsplit")
        self.nvim.command("vertical resize 65")
        self.chat_win = self.nvim.current.window
        self.nvim.current.buffer = self.chat_buf

        # Create input buffer
        self.input_buf = self.nvim.request("nvim_create_buf", False, True)
        self.input_buf.options["buftype"] = "nofile"
        self.input_buf.options["modifiable"] = True
        self.input_buf.name = " "

        self._show_chat_windows()
        self._set_chat_buf_keymaps()

    def _show_chat_windows(self):
        # Create input window as horizontal split
        self.nvim.command("split")
        self.nvim.command("resize 5")
        self.input_win = self.nvim.current.window
        self.nvim.current.buffer = self.input_buf

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
        # If windows exist and are valid, focus them
        if self.chat_win and self.chat_win.valid:
            self.nvim.current.window = self.chat_win
            return

        # If buffers exist but windows don't, just create new windows
        if self.chat_buf and self.chat_buf.valid and self.input_buf and self.input_buf.valid:
            self._show_chat_windows()
            return

        # If nothing exists, create everything new
        self.create_chat_window()

    def close_chat(self):
        if self.input_win and self.input_win.valid:
            self.nvim.api.win_close(self.input_win, True)
        if self.chat_win and self.chat_win.valid:
            self.nvim.api.win_close(self.chat_win, True)

        self.chat_win = None
        self.chat_buf = None
        self.input_win = None
        self.input_buf = None

    def _update_chat_display(self):
        if not self.chat_buf or not self.chat_buf.valid:
            return

        window_width = self.nvim.api.win_get_width(self.chat_win)
        display_lines = [""]
        for msg in self.messages:
            role = msg["role"].upper()
            heading = "#" if role == "USER" else "##"
            padding = " " * ((window_width - len(role) - len(heading)) // 2)
            role_header = f"{heading}{padding}{role}{padding}"

            display_lines.append("---")
            display_lines.append(role_header)
            display_lines.append("---")
            display_lines.append("")

            wrapped_content = msg["content"].split("\n")
            for line in wrapped_content:
                display_lines.append(line)
            display_lines.append("")

        self.chat_buf.options["modifiable"] = True
        self.chat_buf[:] = display_lines
        self.chat_buf.options["modifiable"] = False

        # Scroll to bottom
        self.chat_win.cursor = (len(display_lines), 0)

    def _add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._update_chat_display()

    def _get_input_buf_contents(self) -> Optional[str]:
        if not self.input_buf or not self.input_buf.valid:
            return

        lines = self.input_buf[:]
        message = "\n".join(lines)
        return message.strip()

    def _reset_cursor(self):
        # Reset cursor and keep insert mode
        self.input_win.cursor = (1, 0)
        self.nvim.command("startinsert")

    def send_message(self):
        message = self._get_input_buf_contents()
        if message:
            # Clear input buffer
            self.input_buf[:] = [""]

            # Add user message to chat
            self._add_message("user", message)

            # Get response from LLM
            response = self.llm_provider.anthropic_complete(self.messages)
            if response:
                self._add_message("assistant", response)

        self._reset_cursor()

    def send_message_stream(self):
        message = self._get_input_buf_contents()
        if message:

            def stream_callback(chunk: str) -> None:
                if self.messages[-1].get("role", "") == "user":
                    self.messages.append({"role": "assistant", "content": ""})

                prev_message = self.messages[-1]
                prev_message["content"] = prev_message["content"] + chunk
                self._update_chat_display()

            self.input_buf[:] = [""]
            self._add_message("user", message)
            self.llm_provider.anthropic_complete_stream(self.messages, stream_callback)

        self._reset_cursor()
