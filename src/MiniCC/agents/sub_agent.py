"""SubAgent - 独立上下文的 ReAct 子任务执行器。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from MiniCC.core.agent import Agent
from MiniCC.core.context_compactor import ContextCompactor
from MiniCC.core.workspace_sandbox import get_workspace_sandbox
from MiniCC.core.state_manager import AgentStateManager
from MiniCC.core.tool_policy import resolve_sub_agent_tools
from MiniCC.messages import SystemMessage
from MiniCC.prompts.sub_agent_prompts import SUB_AGENT_SYSTEM_PROMPT
from MiniCC.tools.tool_registry import ToolRegistry, get_global_registry

if TYPE_CHECKING:
    from MiniCC.core.llm import LLM
    from MiniCC.tools.base_tool import BaseTool


class SubAgent(Agent):
    """被 TaskTool 调用的子 Agent，拥有隔离的 history 和受限工具集。"""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        llm: "LLM" | None = None,
        state_manager: AgentStateManager | None = None,
    ):
        system_message = SystemMessage(content=SUB_AGENT_SYSTEM_PROMPT)
        self.registry = registry or get_global_registry()
        super().__init__(
            name="SubAgent",
            description="Delegated sub-task executor with isolated context",
            system_message=system_message,
            tools=[],
            registry=self.registry,
            llm=llm,
            state_manager=state_manager or AgentStateManager(),
        )
        self._allowed_tool_names: frozenset[str] = frozenset()
        self._filtered_tools: list["BaseTool"] = []

    def _build_task_prompt(self, goal: str, context: str) -> str:
        parts = [f"Goal: {goal}"]
        if context.strip():
            parts.append(f"\nContext:\n{context}")
        return "\n".join(parts)

    def _resolve_tools(self, allowed_names: frozenset[str]) -> list["BaseTool"]:
        all_by_name = {tool.name: tool for tool in self.registry.get_all_tools()}
        missing = [name for name in allowed_names if name not in all_by_name]
        if missing:
            raise KeyError(f"SubAgent tools not registered: {missing}")
        return [all_by_name[name] for name in sorted(allowed_names)]

    def run(
        self,
        goal: str,
        context: str = "",
        tools: list[str] | None = None,
        max_steps: int = 20,
    ) -> dict[str, Any]:
        """执行单一子任务，返回结构化结果，不污染主 Agent history。"""
        # 延迟导入：避免 tools/__init__.py 的注册副作用触发循环导入
        from MiniCC.agents.react_loop import run_react_loop, split_thinking

        # 复用主 Agent 已配置的全局工作区沙箱
        get_workspace_sandbox()

        allowed_names = resolve_sub_agent_tools(tools)
        self._allowed_tool_names = allowed_names
        self._filtered_tools = self._resolve_tools(allowed_names)

        history: list[Any] = [
            self.system_message,
            SystemMessage(content=self._build_task_prompt(goal, context)),
        ]

        sub_compactor = ContextCompactor()
        result = run_react_loop(
            llm=self.llm,
            registry=self.registry,
            history=history,
            get_tools=lambda: self._filtered_tools,
            compactor=sub_compactor,
            enable_full_compact=False,
            max_steps=max_steps,
            log_label="SubAgent",
        )

        _, body = split_thinking(result.response.content or "")
        final_answer = body or result.response.content or ""

        return {
            "status": result.status,
            "goal": goal,
            "final_answer": final_answer,
            "steps_taken": result.steps_taken,
            "tools_used": result.tools_used,
            "errors": result.errors,
        }
