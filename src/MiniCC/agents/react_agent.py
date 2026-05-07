"""ReActAgent 实现，继承自 core/agent.py 中的 Agent 基类。"""
from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any

from MiniCC.core.agent import Agent
from MiniCC.core.hitl import get_global_approval_manager
from MiniCC.core.logger import get_logger
from MiniCC.messages import AIMessage, SystemMessage, ToolMessage
from MiniCC.prompts import REACT_AGENT_SYSTEM_PROMPT
from MiniCC.tools.tool_registry import ToolRegistry, get_global_registry

if TYPE_CHECKING:
    from MiniCC.core.llm import LLM
    from MiniCC.core.state_manager import AgentStateManager

_log = get_logger("ReActAgent")

# LLM 把 thinking 段落封装在 content 里时使用的边界标记
_THINK_RE = re.compile(
    r"^=== THINKING ===\s*\n(.*?)\n=== END THINKING ===\s*\n*(.*)$",
    re.DOTALL,
)


def _split_thinking(content: str) -> tuple[str, str]:
    """把 LLM content 拆为 (thinking, body)，没有 thinking 时返回 ('', content)。"""
    if not content:
        return "", ""
    m = _THINK_RE.match(content)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", content


class ReActAgent(Agent):
    """ReAct 架构 Agent，继承自 Agent 基类，所有功能通过 Tool Call 实现。"""

    def __init__(
        self,
        name: str = "ReActAgent",
        description: str = "ReAct 驱动的测试生成 Agent",
        system_message: SystemMessage | None = None,
        registry: ToolRegistry | None = None,
        llm: "LLM" | None = None,
        state_manager: "AgentStateManager" | None = None,
    ):
        if system_message is None:
            system_message = SystemMessage(content=REACT_AGENT_SYSTEM_PROMPT)
        self.registry = registry or get_global_registry()
        tools = self.registry.get_all_tools()
        super().__init__(
            name,
            description,
            system_message,
            tools,
            self.registry,
            llm=llm,
            state_manager=state_manager,
        )

        self.history: list[Any] = []

    def run(self, prompt: str) -> AIMessage:
        """ReAct 主循环：Thought → Tool Call → Observation，直到 Final Answer。
        使用 while 循环实现更标准的 ReAct 结构。"""
        self.history = [self.system_message, SystemMessage(content=prompt)]
        _log.section(f"启动 ReAct 循环  ·  user prompt: {prompt!r}")

        max_steps = 50
        step = 0
        while step < max_steps:
            step += 1
            _log.step(step, max_steps)

            current_mode = self.state_manager.get_mode()
            _log.debug(f"当前 mode={current_mode}")
            tools = self.registry.get_tools_for_mode(current_mode)
            response = self.llm.think_with_tools(self.history, tools)

            self.history.append(response)

            thinking, body = _split_thinking(response.content or "")
            if thinking:
                _log.thinking(thinking)
            if body:
                _log.info(body)

            if not getattr(response, "tool_calls", None):
                _log.section("ReAct 循环结束 · Final Answer")
                _log.final_answer(body or response.content or "")
                return response

            for tool_call in getattr(response, "tool_calls", []):
                tool_name = tool_call.function.name
                args = self._parse_tool_arguments(tool_name, tool_call.function.arguments)
                _log.tool_call(tool_name, args)

                t0 = time.perf_counter()
                tool_result = self._execute_tool_with_args(tool_name, args)
                duration_ms = int((time.perf_counter() - t0) * 1000)
                _log.tool_result(tool_name, tool_result, duration_ms=duration_ms)

                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call.id,
                )
                self.history.append(tool_message)

        _log.warn(f"达到最大步数 {max_steps}，任务未完成")
        return AIMessage(content="Max steps reached. Task incomplete.")

    def _execute_tool(self, tool_call: Any) -> Any:
        """根据 Tool Call 执行对应 Tool（从 Registry 获取）。保留向后兼容入口。"""
        tool_name = tool_call.function.name
        args = self._parse_tool_arguments(tool_name, tool_call.function.arguments)
        return self._execute_tool_with_args(tool_name, args)

    def _execute_tool_with_args(self, tool_name: str, args: dict[str, Any]) -> Any:
        """已解析 args 后真正调用 Tool。失败时返回错误描述字符串。

        在真正执行前先过 HITL 审批层；若被用户拒绝，返回结构化的
        ``[HITL Rejected] {reason}`` 字符串，作为 ToolMessage 回灌给 LLM。
        """
        approval_mgr = get_global_approval_manager()
        if approval_mgr.requires_approval(tool_name, args):
            decision = approval_mgr.request(tool_name, args)
            if not decision.approved:
                _log.warn(f"用户拒绝执行 {tool_name}: {decision.reason}")
                return f"[HITL Rejected] {decision.reason}"

        try:
            tool = self.registry.get_tool(tool_name)
            return tool.execute(**args)
        except Exception as e:
            _log.error(f"Tool '{tool_name}' 执行异常: {e}")
            return f"Tool execution error: {e}"

    def _parse_tool_arguments(self, tool_name: str, arguments: str) -> dict[str, Any]:
        """Parse tool arguments and keep the legacy malformed-JSON fallback."""
        arguments_str = arguments.strip()
        try:
            return json.loads(arguments_str)
        except json.JSONDecodeError:
            return self._parse_repaired_arguments(tool_name, arguments_str)

    def _parse_repaired_arguments(self, tool_name: str, arguments_str: str) -> dict[str, Any]:
        """Try the existing lightweight JSON repair before using the legacy fallback."""
        fixed = re.sub(r'([^\\])"(\s*[\}\],])', r'\1\\" \2', arguments_str)
        fixed = re.sub(r"\n", r"\\n", fixed)
        try:
            args = json.loads(fixed)
            _log.warn(f"工具 {tool_name} 的 arguments JSON 格式异常，已自动修复")
            return args
        except Exception:
            _log.error(f"工具 {tool_name} 的 arguments 无法修复，使用兜底参数")
            return {"path": "unknown", "content": arguments_str, "confirm": True}

"""测试"""
if __name__ == "__main__":
    from pydantic import BaseModel

    from MiniCC.tools.base_tool import BaseTool
    from MiniCC.tools.tool_registry import register_tool
    # 触发 plan/filesystem 工具自动注册
    from MiniCC.tools.plan_tool.planner_tool import PlannerTool  # noqa: F401
    from MiniCC.tools.plan_tool.plan_mode_tools import (  # noqa: F401
        EnterPlanModeTool,
        ExitPlanModeTool,
    )
    from MiniCC.tools.filesystem_tool import filesystem_tools  # noqa: F401

    _demo_log = get_logger("Demo")

    class WeatherArgs(BaseModel):
        city: str

    class MockWeatherTool(BaseTool):
        name = "get_weather"
        description = "Get current weather for a city."
        args_schema = WeatherArgs

        def execute(self, **kwargs: Any) -> Any:
            _demo_log.debug(f"MockWeatherTool 调用 args={kwargs}")
            city = kwargs.get("city", "unknown")
            return f"{city} is sunny"

    register_tool(MockWeatherTool())

    agent = ReActAgent()
    response = agent.run(
        "在project目录下写一个俄罗斯方块小游戏只用python自带库不用其他库，并写一个测试用例测试这个游戏"
    )
    _demo_log.final_answer(response.content or "")

