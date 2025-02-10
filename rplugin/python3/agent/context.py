import logging
import os
from typing import Dict, List

import pynvim
from pynvim.api import Buffer

from .llm.constants import FILE_TREE_IGNORE_PATTERNS, SYSTEM_PROMPT
from .llm.types import FileContext

IGNORED_BUF_FILE_TYPES = {"alpha", "unkown", "NvimTree", "TelescopePrompt", "TelescopeResult", "agent.nvim"}
IGNORED_BUF_PATTERNS = {"agent chat", "NvimTree", "diffview", ".log", ".git"}


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

    @property
    def cwd(self) -> str:
        return self.nvim.call("getcwd")

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

    def _get_directory_tree(
        self,
        max_depth: int = 3,
        include_hidden: bool = False,
    ) -> str:
        """Generate a tree representation of the directory structure."""

        def should_include(entry: str, path: str) -> bool:
            # Skip hidden files unless explicitly enabled
            if not include_hidden and entry.startswith("."):
                return False

            # Skip ignored patterns
            if any(pattern in path for pattern in FILE_TREE_IGNORE_PATTERNS):
                return False

            return True

        def build_tree(directory: str, prefix: str = "", current_depth: int = 0) -> str:
            if current_depth > max_depth:
                return ""

            tree = ""
            try:
                entries = os.listdir(directory)
                # Filter and sort entries
                entries = [e for e in sorted(entries) if should_include(e, os.path.join(directory, e))]

                for i, entry in enumerate(entries):
                    path = os.path.join(directory, entry)
                    is_last = i == len(entries) - 1
                    current_prefix = "└── " if is_last else "├── "

                    tree += f"{prefix}{current_prefix}{entry}\n"

                    if os.path.isdir(path):
                        next_prefix = prefix + ("    " if is_last else "│   ")
                        tree += build_tree(path, next_prefix, current_depth + 1)
            except (PermissionError, FileNotFoundError):
                pass

            return tree

        tree = build_tree(self.cwd)
        return tree if tree else ""

    def get_system_prompt_with_context(self):
        return SYSTEM_PROMPT.replace("{{CWD}}", self.cwd).replace("{{DIRECTORY_TREE}}", self._get_directory_tree())

    def get_file_context(self) -> FileContext:
        active_buffers = [buf.name for buf in self.get_active_buffers()]
        context_files = self.get_additional_files()
        return FileContext(active_buffers=active_buffers, files=context_files)

    def reload_buffer(self, buf: Buffer) -> None:
        """Reload a buffer's content from disk without changing window focus.

        Args:
            buf: The buffer to reload
        """
        with open(buf.name, "r") as f:
            content = f.read().splitlines()
        buf[:] = content
        # Mark buffer as unmodified since it now matches the file
        buf.options["modified"] = False

    def get_active_buffer_for_path(self, file_path: str) -> Buffer | None:
        """Check if a file path matches any active buffer and return the buffer if found.

        Args:
            file_path: Either absolute or relative path to check

        Returns:
            Buffer | None: The matching buffer if found, None otherwise
        """
        if not file_path:
            return None

        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.cwd, file_path)

        # Normalize paths for comparison
        file_path = os.path.normpath(file_path)

        # Check against active buffers
        for buf in self.get_active_buffers():
            buf_path = os.path.normpath(buf.name)
            if buf_path == file_path:
                return buf

        return None

    def delete_active_buffer(self, bufnr: int):
        if bufnr in self.active_buffers:
            self.nvim.api.buf_delete(bufnr, {"force": True})
            del self.active_buffers[bufnr]
