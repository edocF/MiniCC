"""Finish Tool 用于 ReAct 循环终止。"""
from pydantic import BaseModel
from MiniCC.tools.base_tool import BaseTool

# 自动注册到全局 Registry
from MiniCC.tools.tool_registry import register_tool


class FinishArgs(BaseModel):
    reason: str


class FinishTool(BaseTool):
    name = "finish"
    description = "Call this tool when the task is complete or cannot continue."
    args_schema = FinishArgs

    def execute(self, reason: str) -> str:
        return f"Task finished. Reason: {reason}"


# 模块加载时自动注册
register_tool(FinishTool())
