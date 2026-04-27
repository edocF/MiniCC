"""AgentStateManager - 集中管理 Agent 的运行时状态，使用字符串 mode ("active", "plan")。
ReActAgent 持有此管理器，工具通过它切换状态。"""
from typing import Any

from pydantic import BaseModel, Field

from MiniCC.core.tool_policy import get_allowed_tool_names, normalize_mode


class AgentState(BaseModel):
    """Agent 当前运行状态。"""
    mode: str = "active"  # "active" 或 "plan"
    current_plan: dict[str, Any] = Field(default_factory=dict)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    round_index: int = 0


class AgentStateManager:
    """集中式的 Agent 状态管理中心。"""

    def __init__(self):
        self.state = AgentState()

    def set_mode(self, mode: str) -> None:
        """切换模式。支持 'active' 和 'plan'。"""
        mode = normalize_mode(mode)
        self.state.mode = mode
        print(f"[StateManager] Mode changed to: {mode}")

    def get_mode(self) -> str:
        return self.state.mode

    def update_plan(self, plan: dict[str, Any]) -> None:
        self.state.current_plan = plan
        self.set_mode("active")  # 生成计划后自动回到 active 模式

    def add_context(self, key: str, value: Any) -> None:
        self.state.context_summary[key] = value

    def get_allowed_tool_names(self, mode: str) -> set[str]:
        """返回当前 mode 允许的工具名集合。"""
        return set(get_allowed_tool_names(mode))

    def get_state_summary(self) -> str:
        return f"Current Mode: {self.state.mode}, Plan: {'Yes' if self.state.current_plan else 'No'}"


# 全局单例（供工具使用）
_global_state_manager = AgentStateManager()


def get_global_state_manager() -> AgentStateManager:
    """获取全局状态管理器。"""
    return _global_state_manager
