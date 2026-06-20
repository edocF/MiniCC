"""会话内 PlanningState 与 todo 待办管理器。

该模块实现“会话外显计划状态（s03）”：主循环在多步任务中持续维护
一份可读的待办列表，并在连续多轮未更新时注入 reminder。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanItem(BaseModel):
    """单条待办条目。"""

    content: str
    status: Literal["pending", "in_progress", "completed"] = "pending"
    activeForm: str = ""


class PlanningState(BaseModel):
    """当前会话的规划状态（仅用于本会话，不做持久化）。"""

    items: list[PlanItem] = Field(default_factory=list)
    rounds_since_update: int = 0


class TodoManager:
    """维护 PlanningState：更新、渲染与 reminder 触发。"""

    REMINDER_THRESHOLD = 3

    def __init__(self, state: PlanningState | None = None) -> None:
        self.state = state or PlanningState()

    def reset(self) -> None:
        self.state.items = []
        self.state.rounds_since_update = 0

    def update(self, items: list[PlanItem] | list[dict[str, Any]]) -> str:
        parsed_items: list[PlanItem] = []
        for item in items:
            if isinstance(item, PlanItem):
                parsed_items.append(item)
            else:
                parsed_items.append(PlanItem.model_validate(item))

        in_progress_count = sum(1 for it in parsed_items if it.status == "in_progress")
        if in_progress_count > 1:
            raise ValueError("Only one item can be in_progress at the same time.")

        self.state.items = parsed_items
        self.state.rounds_since_update = 0
        return self.render()

    def render(self) -> str:
        marker = {
            "pending": "[ ]",
            "in_progress": "[>]",
            "completed": "[x]",
        }

        if not self.state.items:
            return "(no plan items)"

        lines: list[str] = []
        for it in self.state.items:
            text = (it.activeForm or it.content).strip()
            lines.append(f"{marker[it.status]} {text}")
        return "\n".join(lines)

    def tick_round(self, *, used_todo: bool) -> None:
        if used_todo:
            self.state.rounds_since_update = 0
            return
        self.state.rounds_since_update += 1

    def get_reminder_text(self) -> str | None:
        # 只在阈值刚好到达时提醒一次，避免每轮都注入造成上下文膨胀
        if not self.state.items:
            return None
        if self.state.rounds_since_update != self.REMINDER_THRESHOLD:
            return None
        return (
            "<reminder>Refresh your plan with the todo tool before continuing.</reminder>\n"
            "Current plan:\n"
            f"{self.render()}"
        )

