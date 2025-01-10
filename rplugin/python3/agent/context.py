import logging
from typing import Dict, List

import pynvim
from pynvim.api import Buffer

IGNORED_BUF_FILE_TYPES = {"alpha", "unkown", "NvimTree", "TelescopePrompt", "TelescopeResult", "agent_input"}
IGNORED_BUF_PATTERNS = {"agent chat"}


logger = logging.getLogger(__name__)


class ContextBuf:
    def __init__(self, buf: Buffer):
        self.buf = buf
        self.is_active = True


class AgentContext:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.active_buffers: Dict[int, ContextBuf] = {}
        self.additional_files: List[str] = []
        self._refresh_active_buffers()

    def _refresh_active_buffers(self):
        for buf in self.nvim.buffers:
            if buf.valid and buf.name and not self._is_ignored_buffer(buf):
                if buf.number not in self.active_buffers:
                    self.active_buffers[buf.number] = ContextBuf(buf)

    def _is_ignored_buffer(self, buf: Buffer) -> bool:
        """Check if buffer should be ignored in context"""
        if not buf.valid or not buf.name:
            return True
        filetype = buf.options.get("filetype", "unknown")
        is_ignored_file_type = filetype in IGNORED_BUF_FILE_TYPES
        is_ignored_pattern = any([pattern in buf.name for pattern in IGNORED_BUF_PATTERNS])
        return is_ignored_file_type or is_ignored_pattern

    def get_context_data(self) -> Dict:
        """Get current context data in a format suitable for the previewer"""
        self._refresh_active_buffers()
        buffers = []
        for buf_num, ctx_buf in self.active_buffers.items():
            buffers.append({"number": buf_num, "name": ctx_buf.buf.name, "active": ctx_buf.is_active})

        return {"buffers": buffers, "files": self.additional_files}

    def add_file(self, file_path: str):
        """Add a file to the context"""
        if file_path and file_path not in self.additional_files:
            self.additional_files.append(file_path)

    def remove_file(self, file_path: str):
        """Remove a file from the context"""
        if file_path in self.additional_files:
            self.additional_files.remove(file_path)

    def get_additional_files(self) -> List[str]:
        return self.additional_files

    def clear_additional_files(self):
        """Clear all additional files from context"""
        self.additional_files = []

    def get_active_buffers(self) -> List[Buffer]:
        self._refresh_active_buffers()
        return [ctx_buf.buf for ctx_buf in self.active_buffers.values() if ctx_buf.is_active]

    def clear_active_buffers(self):
        """Deactivate all buffers in context"""
        for ctx_buf in self.active_buffers.values():
            ctx_buf.is_active = False

    def toggle_buffer(self, buf_number: int):
        """Toggle buffer active state"""
        if buf_number in self.active_buffers:
            ctx_buf = self.active_buffers[buf_number]
            ctx_buf.is_active = not ctx_buf.is_active
