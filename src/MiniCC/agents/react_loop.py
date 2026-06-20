"""Shared ReAct loop logic for ReActAgent and SubAgent."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from MiniCC.core.context_compactor import ContextCompactor
from MiniCC.core.hitl import get_global_approval_manager
from MiniCC.core.logger import get_logger
from MiniCC.core.tool_args_parser import parse_tool_arguments
from MiniCC.messages import AIMessage, SystemMessage, ToolMessage
from MiniCC.tools.tool_registry import ToolRegistry

_log = get_logger("ReActLoop")

_THINK_RE = re.compile(
    r"^=== THINKING ===\s*\n(.*?)\n=== END THINKING ===\s*\n*(.*)$",
    re.DOTALL,
)

LoopStatus = Literal["success", "max_steps", "failed"]


@dataclass
class LoopResult:
    """Result of a ReAct loop execution."""

    status: LoopStatus
    response: AIMessage
    steps_taken: int
    tools_used: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    history: list[Any] = field(default_factory=list)


def split_thinking(content: str) -> tuple[str, str]:
    """Split LLM content into (thinking, body)."""
    if not content:
        return "", ""
    match = _THINK_RE.match(content)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", content


_TRUNCATION_ERROR = (
    "[Tool Args Error] LLM 输出被截断（finish_reason=length）。"
    "请拆分为多次 write_file（append=true）或减小单次 content 体积后重试，"
    "不得重复相同大体量调用。"
)


def _track_recent_files(
    compactor: ContextCompactor | None,
    tool_name: str,
    args: dict[str, Any],
) -> None:
    if compactor is None:
        return
    if tool_name in {"read_file", "write_file", "edit_file", "delete_file", "grep"}:
        path = args.get("path")
        if isinstance(path, str):
            compactor.track_recent_file(path)


def execute_tool_with_args(
    registry: ToolRegistry,
    tool_name: str,
    args: dict[str, Any],
) -> Any:
    """Execute a tool with HITL approval. Returns result or error string."""
    approval_mgr = get_global_approval_manager()
    if approval_mgr.requires_approval(tool_name, args):
        decision = approval_mgr.request(tool_name, args)
        if not decision.approved:
            _log.warn(f"用户拒绝执行 {tool_name}: {decision.reason}")
            return f"[HITL Rejected] {decision.reason}"

    try:
        tool = registry.get_tool(tool_name)
        return tool.execute(**args)
    except Exception as exc:
        _log.error(f"Tool '{tool_name}' 执行异常: {exc}")
        return f"Tool execution error: {exc}"


def run_react_loop(
    *,
    llm: Any,
    registry: ToolRegistry,
    history: list[Any],
    get_tools: Callable[[], list[Any]],
    state_manager: Any | None = None,
    compactor: ContextCompactor | None = None,
    enable_full_compact: bool = True,
    max_steps: int,
    log_label: str = "ReAct",
) -> LoopResult:
    """Run the ReAct Thought → Tool Call → Observation loop."""
    tools_used: list[dict[str, Any]] = []
    errors: list[str] = []
    step = 0
    final_response: AIMessage | None = None

    _log.section(f"启动 {log_label} 循环  ·  max_steps={max_steps}")

    while step < max_steps:
        step += 1
        _log.step(step, max_steps)

        used_todo = False
        reminder = (
            state_manager.get_planning_reminder() if state_manager else None
        )
        if reminder:
            history.append(SystemMessage(content=reminder))

        if compactor is not None:
            history = compactor.prepare_context(
                history,
                llm=llm if enable_full_compact else None,
                state_manager=state_manager if enable_full_compact else None,
                enable_full_compact=enable_full_compact,
            )

        tools = get_tools()
        try:
            response = llm.think_with_tools(history, tools)
        except Exception as exc:
            _log.error(f"{log_label} LLM 调用失败: {exc}")
            errors.append(str(exc))
            return LoopResult(
                status="failed",
                response=AIMessage(content=f"LLM error: {exc}"),
                steps_taken=step,
                tools_used=tools_used,
                errors=errors,
                history=history,
            )

        history.append(response)

        thinking, body = split_thinking(response.content or "")
        if thinking:
            _log.thinking(thinking)
        if body:
            _log.info(body)

        if not getattr(response, "tool_calls", None):
            _log.section(f"{log_label} 循环结束 · Final Answer")
            _log.final_answer(body or response.content or "")
            if state_manager:
                state_manager.on_loop_step_end(used_todo=used_todo)
            return LoopResult(
                status="success",
                response=response,
                steps_taken=step,
                tools_used=tools_used,
                errors=errors,
                history=history,
            )

        response_meta = getattr(response, "metadata", None) or {}
        output_truncated = bool(response_meta.get("truncated"))

        for tool_call in getattr(response, "tool_calls", []):
            tool_name = tool_call.function.name

            if output_truncated:
                tool_result = _TRUNCATION_ERROR
                _log.error(f"跳过 {tool_name}：LLM 输出被截断")
                tools_used.append({"name": tool_name, "args": None, "skipped": "truncated"})
            else:
                parse_result = parse_tool_arguments(
                    tool_name, tool_call.function.arguments
                )
                if parse_result.error:
                    tool_result = f"[Tool Args Error] {parse_result.error}"
                    _log.error(f"跳过 {tool_name}：{parse_result.error}")
                    tools_used.append({
                        "name": tool_name,
                        "args": None,
                        "skipped": "parse_error",
                        "is_truncated": parse_result.is_truncated,
                    })
                    errors.append(tool_result)
                else:
                    args = parse_result.args or {}
                    _log.tool_call(tool_name, args)
                    tools_used.append({"name": tool_name, "args": args})
                    _track_recent_files(compactor, tool_name, args)

                    started = time.perf_counter()
                    tool_result = execute_tool_with_args(registry, tool_name, args)
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    _log.tool_result(tool_name, tool_result, duration_ms=duration_ms)

                    if isinstance(tool_result, str) and tool_result.startswith(
                        "Tool execution error:"
                    ):
                        errors.append(tool_result)

            tool_content = str(tool_result)
            if compactor is not None:
                tool_content = compactor.persist_large_output(
                    tool_call.id, tool_content
                )

            history.append(
                ToolMessage(
                    content=tool_content,
                    tool_call_id=tool_call.id,
                )
            )
            if tool_name.lower() == "todo":
                used_todo = True

        if state_manager:
            state_manager.on_loop_step_end(used_todo=used_todo)

    _log.warn(f"达到最大步数 {max_steps}，任务未完成")
    final_response = AIMessage(content="Max steps reached. Task incomplete.")
    return LoopResult(
        status="max_steps",
        response=final_response,
        steps_taken=step,
        tools_used=tools_used,
        errors=errors,
        history=history,
    )
