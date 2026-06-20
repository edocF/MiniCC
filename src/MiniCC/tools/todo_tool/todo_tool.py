"""todo 工具：会话内外显计划（s03）写入入口。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from MiniCC.core.state_manager import get_global_state_manager
from MiniCC.tools.base_tool import BaseTool


class TodoItemArgs(BaseModel):
    content: str = Field(..., description="This todo item content.")
    status: Literal["pending", "in_progress", "completed"] = Field(
        "pending",
        description="Todo status. There must be at most one in_progress item.",
    )
    activeForm: str = Field("", description="Optional 'in progress' phrase.")


class TodoArgs(BaseModel):
    items: list[TodoItemArgs] = Field(..., description="Replace the current todo list.")


class TodoTool(BaseTool):
    name = "todo"
    description = (
        "Update the current session plan as an external todo panel. "
        "Pass the full list of items each time. "
        "Statuses: pending, in_progress (at most one), completed. "
        "Use it at the start of multi-step work and refresh after each step."
    )
    args_schema = TodoArgs

    def execute(self, items: list[TodoItemArgs], **_: Any) -> str:
        return get_global_state_manager().update_todo(items)


# Module import side-effect: register tool
from MiniCC.tools.tool_registry import register_tool  # noqa: E402

register_tool(TodoTool())

