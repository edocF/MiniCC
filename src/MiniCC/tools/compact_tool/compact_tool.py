"""compact 工具：手动触发完整上下文压缩（s06 Layer 3）。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from MiniCC.core.state_manager import get_global_state_manager
from MiniCC.tools.base_tool import BaseTool


class CompactArgs(BaseModel):
    reason: str = Field("", description="Optional reason for compacting context now")


class CompactTool(BaseTool):
    name = "compact"
    description = (
        "Manually compact conversation history to free context while preserving continuity. "
        "Summarizes goal, progress, files, and next steps. "
        "Use when context is getting large or before a major new phase of work."
    )
    args_schema = CompactArgs

    def execute(self, reason: str = "") -> str:
        state_manager = get_global_state_manager()
        state_manager.request_compact()
        suffix = f" Reason: {reason}" if reason else ""
        return (
            "Compact requested. The next LLM turn will summarize history "
            f"while preserving goal, todo plan, and recent files.{suffix}"
        )


from MiniCC.tools.tool_registry import register_tool  # noqa: E402

register_tool(CompactTool())
