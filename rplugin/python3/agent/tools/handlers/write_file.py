import logging

from ...llm.types import TextToolResult
from .base import ToolHandler

logger = logging.getLogger(__name__)


class WriteFileHandler(ToolHandler):
    """Handler for the edit tool"""

    @property
    def name(self) -> str:
        return "write_file"

    def handle_result(self, tool_result: TextToolResult):
        tool_call = self._tool_use_map[tool_result.tool_use_id]
        logger.debug("write_file result")
        logger.debug(tool_call)

        file_path = tool_call.input.get("path")
        if file_path:
            active_buf = self._context.get_active_buffer_for_path(file_path)
            if active_buf:
                logger.debug(f"Writing to active buffer: {active_buf.name}")
                self._context.reload_buffer(active_buf)
            else:
                logger.debug("Writing non-active buffer or file")
