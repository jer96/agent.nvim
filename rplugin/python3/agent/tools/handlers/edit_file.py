import logging

from ...llm.types import TextToolResult
from .base import ToolHandler

logger = logging.getLogger(__name__)


class EditFileHandler(ToolHandler):
    """Handler for the edit tool"""

    @property
    def name(self) -> str:
        return "edit_file"

    def handle_result(self, tool_result: TextToolResult):
        tool_call = self._tool_use_map[tool_result.tool_use_id]
        logger.debug("edit_tool result")

        file_path = tool_call.input.get("path")
        is_dry_run = tool_call.input.get("dryRun", False)
        if file_path:
            active_buf = self._context.get_active_buffer_for_path(file_path)
            logger.debug(f"is_dry_run: {is_dry_run}")
            if active_buf:
                logger.debug(f"Editing active buffer: {active_buf.name}")
                if not is_dry_run:
                    self._context.reload_buffer(active_buf)
            else:
                logger.debug("Editing non-active buffer or file")
