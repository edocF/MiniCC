"""Task Tool - 将子任务委托给独立 SubAgent 执行。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from MiniCC.agents.sub_agent import SubAgent
from MiniCC.core.llm import LLM
from MiniCC.core.logger import get_logger
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import get_global_registry

_log = get_logger("TaskTool")


class TaskArgs(BaseModel):
    goal: str = Field(..., description="The focused sub-task goal for the SubAgent")
    context: str = Field(
        "",
        description="Summarized context from the main Agent (not full conversation history)",
    )
    tools: list[str] | None = Field(
        None,
        description="Optional subset of sub-agent tools; must be within the default allowlist",
    )
    max_steps: int = Field(20, ge=1, le=50, description="Maximum ReAct steps for the SubAgent")


class TaskTool(BaseTool):
    name = "task"
    description = (
        "Delegate a focused sub-task to an isolated SubAgent with its own context. "
        "The SubAgent can use readonly and active tools (read/write/execute) but cannot "
        "recursively call task, planner, or plan_mode tools. "
        "Pass only a concise context summary, not the full conversation. "
        "Returns structured result with status, final_answer, and tools_used."
    )
    args_schema = TaskArgs

    def __init__(self):
        super().__init__()
        self.llm = LLM()

    def execute(
        self,
        goal: str,
        context: str = "",
        tools: list[str] | None = None,
        max_steps: int = 20,
    ) -> dict[str, Any]:
        """Spawn a SubAgent, run the sub-task, and return structured output."""
        _log.info(f"委托子任务  goal={goal!r}  max_steps={max_steps}")
        if tools and "task" in tools:
            _log.warn("主 Agent 在 tools 参数中传入了 task，将被忽略")

        try:
            sub_agent = SubAgent(registry=get_global_registry(), llm=self.llm)
            result = sub_agent.run(
                goal=goal,
                context=context,
                tools=tools,
                max_steps=max_steps,
            )
            _log.success(
                f"子任务完成  status={result['status']}  steps={result['steps_taken']}"
            )
            return result
        except Exception as exc:
            _log.error(f"子任务执行失败: {exc}")
            return {
                "status": "failed",
                "goal": goal,
                "final_answer": "",
                "steps_taken": 0,
                "tools_used": [],
                "errors": [str(exc)],
            }
