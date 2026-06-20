"""ReActAgent 实现，继承自 core/agent.py 中的 Agent 基类。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

from MiniCC.agents.react_loop import run_react_loop
from MiniCC.core.agent import Agent
from MiniCC.core.logger import get_logger
from MiniCC.core.workspace_sandbox import WorkspaceNotConfiguredError, configure_workspace
from MiniCC.messages import AIMessage, SystemMessage
from MiniCC.prompts import REACT_AGENT_SYSTEM_PROMPT
from MiniCC.tools.tool_registry import ToolRegistry, get_global_registry

if TYPE_CHECKING:
    from MiniCC.core.llm import LLM
    from MiniCC.core.state_manager import AgentStateManager

_log = get_logger("ReActAgent")


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
        workspace_root: str | Path | None = None,
    ):
        load_dotenv()
        project_env = Path(__file__).resolve().parents[4] / ".env"
        if project_env.is_file():
            load_dotenv(project_env)
        root = workspace_root or os.getenv("MINICC_WORKSPACE_ROOT")
        if not root:
            raise WorkspaceNotConfiguredError(
                "workspace_root is required. Pass workspace_root=... to ReActAgent "
                "or set environment variable MINICC_WORKSPACE_ROOT."
            )
        configure_workspace(root)
        _log.info(f"工作区沙箱已配置  root={Path(root).resolve()}")

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
        """ReAct 主循环：Thought → Tool Call → Observation，直到 Final Answer。"""
        self.state_manager.reset_planning()
        self.state_manager.reset_compact()
        if hasattr(self.llm, "reset_token_usage"):
            self.llm.reset_token_usage()
        self.history = [self.system_message, SystemMessage(content=prompt)]
        _log.section(f"启动 ReAct 循环  ·  user prompt: {prompt!r}")

        compactor = self.state_manager.get_compactor()
        result = run_react_loop(
            llm=self.llm,
            registry=self.registry,
            history=self.history,
            get_tools=lambda: self.registry.get_tools_for_mode(self.state_manager.get_mode()),
            state_manager=self.state_manager,
            compactor=compactor,
            enable_full_compact=True,
            max_steps=50,
            log_label="ReAct",
        )
        self.history = result.history
        if hasattr(self.llm, "get_token_usage"):
            usage = self.llm.get_token_usage()
            _log.info(
                "Agent Run token 总计  "
                f"prompt={usage.get('prompt_tokens', 0)}  "
                f"completion={usage.get('completion_tokens', 0)}  "
                f"total={usage.get('total_tokens', 0)}"
            )
        return result.response

