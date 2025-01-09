import logging
from typing import Dict, List

import pynvim
from pynvim.api import Buffer

IGNORED_BUF_FILE_TYPES = {"alpha", "unkown", "NvimTree", "TelescopePrompt", "TelescopeResult", "agent_input"}
IGNORED_BUF_PATTERNS = {"agent chat"}


logger = logging.getLogger(__name__)


class AgentContext:
    def __init__(self, nvim: pynvim.Nvim):
        self.nvim = nvim
        self.active_buffers: Dict[int, Buffer] = {}
        self.additional_files: List[str] = []
        self._refresh_active_buffers()

    def _refresh_active_buffers(self):
        for buf in self.nvim.buffers:
            logger.debug(f"found buf {buf.name}")
            if buf.valid and buf.name and not self._is_ignored_buffer(buf):
                logger.debug(f"found active buf {buf.name}")
                self.active_buffers[buf.number] = buf

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
        for buf in self.active_buffers.values():
            buffers.append({"number": buf.number, "name": buf.name, "active": True})

        return {"buffers": buffers, "files": self.additional_files}

    def add_file(self, file_path: str):
        """Add a file to the context"""
        if file_path and file_path not in self.additional_files:
            self.additional_files.append(file_path)

    def remove_file(self, file_path: str):
        """Remove a file from the context"""
        if file_path in self.additional_files:
            self.additional_files.remove(file_path)

    def get_active_buffers(self) -> List[Buffer]:
        self._refresh_active_buffers()
        return self.active_buffers.values()

    def get_additional_files(self) -> List[str]:
        return self.additional_files
