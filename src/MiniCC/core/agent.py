"""Agent 抽象基类（ReAct 架构修订版）。ReActAgent 将继承此类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from MiniCC.core.llm import LLM
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import ToolRegistry
from MiniCC.core.state_manager import get_global_state_manager

if TYPE_CHECKING:
    from MiniCC.messages.ai_message import AIMessage
    from MiniCC.messages.system_message import SystemMessage
    from MiniCC.core.state_manager import AgentStateManager


class Agent(ABC):
    """所有 Agent 的基类。ReActAgent 继承此类实现 ReAct 循环。"""

    def __init__(
        self,
        name: str,
        description: str,
        system_message: "SystemMessage",
        tools: list[BaseTool] | None = None,
        registry: ToolRegistry | None = None,
        llm: LLM | None = None,
        state_manager: "AgentStateManager" | None = None,
    ):
        self.name = name
        self.description = description
        self.llm = llm or LLM()
        self.system_message = system_message
        self.registry = registry
        self.tools = tools or []
        self.history: list[Any] = []  # Message history for ReAct
        self.state_manager = state_manager or get_global_state_manager()

    def add_tool(self, tool: BaseTool) -> None:
        """动态添加 Tool。"""
        if tool not in self.tools:
            self.tools.append(tool)

    def get_tools(self) -> list[BaseTool]:
        """返回可用 Tool 列表，优先从 registry 获取。"""
        if self.registry is not None:
            return self.registry.get_all_tools()
        return self.tools

    @abstractmethod
    def run(self, prompt: str) -> "AIMessage":
        """ReAct 主循环入口，由子类实现。"""
        pass

    def reset(self) -> None:
        """重置历史，用于新会话。"""
        self.history = [self.system_message]

    def set_mode(self, mode: str) -> None:
        """切换模式。通过状态中心统一管理。"""
        self.state_manager.set_mode(mode)
