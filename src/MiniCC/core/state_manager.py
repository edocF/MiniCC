"""AgentStateManager - 集中管理 Agent 的运行时状态，使用字符串 mode ("active", "plan")。
ReActAgent 持有此管理器，工具通过它切换状态。"""
from typing import Any

from pydantic import BaseModel, Field

from MiniCC.core.context_compactor import CompactState, ContextCompactor
from MiniCC.core.logger import get_logger
from MiniCC.core.tool_policy import get_allowed_tool_names, normalize_mode
from MiniCC.core.todo_manager import PlanningState, TodoManager

_log = get_logger("StateManager")


class AgentState(BaseModel):
    """Agent 当前运行状态。"""
    mode: str = "active"  # "active" 或 "plan"
    current_plan: dict[str, Any] = Field(default_factory=dict)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    round_index: int = 0
    # 会话内规划状态（s03）：用于 todo 工具驱动的外显进度面板
    planning: PlanningState = Field(default_factory=PlanningState)
    # 会话内压缩状态（s06）
    compact: CompactState = Field(default_factory=CompactState)


class AgentStateManager:
    """集中式的 Agent 状态管理中心。"""

    def __init__(self):
        self.state = AgentState()
        self._todo_manager = TodoManager(self.state.planning)
        self._compactor = ContextCompactor(self.state.compact)

    def set_mode(self, mode: str) -> None:
        """切换模式。支持 'active' 和 'plan'。"""
        mode = normalize_mode(mode)
        old = self.state.mode
        self.state.mode = mode
        if old != mode:
            _log.mode_change(old, mode)

    def get_mode(self) -> str:
        return self.state.mode

    def update_plan(self, plan: dict[str, Any]) -> None:
        self.state.current_plan = plan
        self.set_mode("active")  # 生成计划后自动回到 active 模式

    # ==================== s03: todo 规划状态 ====================
    def reset_planning(self) -> None:
        """重置当前会话的 todo 规划状态。"""
        self._todo_manager.reset()

    def update_todo(self, items: list[Any]) -> str:
        """更新当前会话的 todo 条目，并返回渲染后的计划文本。"""
        return self._todo_manager.update(items)

    def render_todo(self) -> str:
        """返回当前 todo 计划的渲染文本。"""
        return self._todo_manager.render()

    def on_loop_step_end(self, *, used_todo: bool) -> None:
        """在每个主循环 step 结束时记录“是否更新了 todo”。"""
        self._todo_manager.tick_round(used_todo=used_todo)

    def get_planning_reminder(self) -> str | None:
        """在合适轮次返回 reminder 文本，否则返回 None。"""
        return self._todo_manager.get_reminder_text()

    # ==================== s06: context compression ====================
    def get_compactor(self) -> ContextCompactor:
        return self._compactor

    def reset_compact(self) -> None:
        """重置当前会话的压缩状态。"""
        self._compactor.reset()

    def request_compact(self) -> None:
        """标记下一轮主循环执行完整压缩。"""
        self._compactor.request_compact()

    def consume_compact_request(self) -> bool:
        return self._compactor.consume_compact_request()

    def record_recent_file(self, path: str) -> None:
        self._compactor.track_recent_file(path)

    def mark_compacted(self, summary: str) -> None:
        self._compactor.mark_compacted(summary)

    def add_context(self, key: str, value: Any) -> None:
        self.state.context_summary[key] = value

    def get_allowed_tool_names(self, mode: str) -> set[str]:
        """返回当前 mode 允许的工具名集合。"""
        return set(get_allowed_tool_names(mode))

    def get_state_summary(self) -> str:
        return (
            f"Current Mode: {self.state.mode}, Plan: {'Yes' if self.state.current_plan else 'No'}, "
            f"TodoItems: {len(self.state.planning.items)}, "
            f"Compacted: {self.state.compact.has_compacted}"
        )


# 全局单例（供工具使用）
_global_state_manager = AgentStateManager()


def get_global_state_manager() -> AgentStateManager:
    """获取全局状态管理器。"""
    return _global_state_manager
