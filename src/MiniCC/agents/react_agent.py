"""ReActAgent 实现，继承自 core/agent.py 中的 Agent 基类。"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from MiniCC.core.agent import Agent
from MiniCC.messages import AIMessage, SystemMessage, ToolMessage
from MiniCC.prompts import REACT_AGENT_SYSTEM_PROMPT
from MiniCC.tools.tool_registry import ToolRegistry, get_global_registry

if TYPE_CHECKING:
    from MiniCC.core.llm import LLM
    from MiniCC.core.state_manager import AgentStateManager


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

        max_steps = 50
        step = 0
        while step < max_steps:
            # LLM 思考并可能调用 Tool，根据当前 mode 过滤工具
            current_mode = self.state_manager.get_mode()
            tools = self.registry.get_tools_for_mode(current_mode)
            response = self.llm.think_with_tools(self.history, tools)

            self.history.append(response)

            # reasoning_content 已直接封装在 content 中，直接打印
            if response.content:
                print(response.content)

            if not getattr(response, "tool_calls", None):
                # Final answer
                return response

            # 执行所有 Tool Call
            for tool_call in getattr(response, "tool_calls", []):
                tool_result = self._execute_tool(tool_call)
                print(f"==============Tool call: {tool_call.function.name}===============")
                print(f"==============Tool result: {tool_result}===============")
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call.id,
                )
                self.history.append(tool_message)

            step += 1

        # 超时返回最后一条消息
        return AIMessage(content="Max steps reached. Task incomplete.")

    def _execute_tool(self, tool_call: Any) -> Any:
        """根据 Tool Call 执行对应 Tool（从 Registry 获取）。支持 PlanMode 切换。
        增强了对格式错误 JSON 的容错能力，特别是 write_file 的 content 包含大量代码时。"""
        try:
            tool_name = tool_call.function.name
            tool = self.registry.get_tool(tool_name)
            args = self._parse_tool_arguments(tool_name, tool_call.function.arguments)
            return tool.execute(**args)
        except Exception as e:
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
            print(f"[JSON Fix] Successfully repaired malformed arguments for {tool_name}")
            return args
        except Exception:
            print(f"[JSON Fix Failed] Using fallback for {tool_name}")
            return {"path": "unknown", "content": arguments_str, "confirm": True}

"""测试"""
if __name__ == "__main__":
    from pydantic import BaseModel

    from MiniCC.messages.user_message import UserMessage
    from MiniCC.tools.base_tool import BaseTool
    from MiniCC.tools.tool_registry import ToolRegistry
    from MiniCC.tools.tool_registry import register_tool
    from MiniCC.tools.plan_tool.planner_tool import PlannerTool
    from MiniCC.tools.plan_tool.plan_mode_tools import EnterPlanModeTool, ExitPlanModeTool
    from MiniCC.tools.filesystem_tool import filesystem_tools  # registers list_dir, glob, read_file, grep
    # registers Enter/Exit tools
    class WeatherArgs(BaseModel):
        city: str
     
    class MockWeatherTool(BaseTool):
        name = "get_weather"
        description = "Get current weather for a city."
        args_schema = WeatherArgs

        def execute(self, **kwargs: Any) -> Any:
            print(f"Executing tool: {kwargs}")
            city = kwargs.get("city", "unknown")
            return f"{city} is sunny"
    
    register_tool(MockWeatherTool())
    # tool_registry = ToolRegistry()
    # tool_registry.register(MockWeatherTool())
    #print(f"Tool registry: {tool_registry.get_all_tools()}")
    agent = ReActAgent()
    print("=== 测试 PlannerTool JSON Mode ===")
    print("使用复杂提示触发 PlanMode -> 只读工具收集 -> Planner (JSON Mode) 生成计划")
    response = agent.run("在project目录下写一个贪吃蛇小游戏只用python语言本地库不用其他库，并写一个测试用例测试这个游戏")
    #response = agent.run("为我在当前目录写一个md文档关于苏州旅游的攻略（我允许创建新文件并写入文件）")
    print("\n=== 最终结果 ===")
    print(response.content)
    print("\n[测试完成] 请检查输出中 Planner 是否使用了 JSON Mode 并生成了结构化计划。")
