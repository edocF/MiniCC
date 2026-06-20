"""Context compression manager (s06): persist, micro-compact, summary compact."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from MiniCC.core.logger import get_logger
from MiniCC.core.output_store import save_tool_output
from MiniCC.messages import SystemMessage, ToolMessage
from MiniCC.messages.user_message import UserMessage
from MiniCC.prompts.compact_prompts import COMPACT_SYSTEM_PROMPT, get_compact_user_prompt

if TYPE_CHECKING:
    from MiniCC.core.state_manager import AgentStateManager

_log = get_logger("ContextCompactor")

PERSIST_THRESHOLD = int(os.getenv("MINICC_PERSIST_THRESHOLD", "8000"))
PREVIEW_LENGTH = 2000
MICRO_COMPACT_KEEP = 5
CONTEXT_LIMIT_CHARS = int(os.getenv("MINICC_CONTEXT_LIMIT", "120000"))
OMITTED_PLACEHOLDER = "[Earlier tool result omitted for brevity]"


class CompactState(BaseModel):
    """Session-level compact tracking (s06)."""

    has_compacted: bool = False
    last_summary: str = ""
    recent_files: list[str] = Field(default_factory=list)
    compact_count: int = 0
    compact_requested: bool = False


class ContextCompactor:
    """Three-layer context compression for ReAct history."""

    def __init__(self, compact_state: CompactState | None = None) -> None:
        self.state = compact_state or CompactState()

    def reset(self) -> None:
        self.state.has_compacted = False
        self.state.last_summary = ""
        self.state.recent_files = []
        self.state.compact_count = 0
        self.state.compact_requested = False

    def request_compact(self) -> None:
        self.state.compact_requested = True

    def consume_compact_request(self) -> bool:
        if not self.state.compact_requested:
            return False
        self.state.compact_requested = False
        return True

    def mark_compacted(self, summary: str) -> None:
        self.state.has_compacted = True
        self.state.last_summary = summary
        self.state.compact_count += 1

    def track_recent_file(self, path: str) -> None:
        if not path or path in {"unknown", ".", ""}:
            return
        if path not in self.state.recent_files:
            self.state.recent_files.append(path)
        if len(self.state.recent_files) > 20:
            self.state.recent_files = self.state.recent_files[-20:]

    def persist_large_output(self, tool_call_id: str, output: str) -> str:
        if len(output) <= PERSIST_THRESHOLD:
            return output

        stored_path = save_tool_output(tool_call_id, output)
        preview = output[:PREVIEW_LENGTH]
        if len(output) > PREVIEW_LENGTH:
            preview += f"\n... ({len(output) - PREVIEW_LENGTH} more chars omitted)"

        _log.info(f"大工具输出已落盘  path={stored_path}  size={len(output)}")
        return (
            "<persisted-output>\n"
            f"Full output saved to: {stored_path}\n"
            f"Preview:\n{preview}\n"
            "</persisted-output>"
        )

    def micro_compact(self, messages: list[Any]) -> list[Any]:
        tool_indices = [
            i for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)
        ]
        if len(tool_indices) <= MICRO_COMPACT_KEEP:
            return messages

        omit_indices = set(tool_indices[:-MICRO_COMPACT_KEEP])
        _log.info(
            "触发微压缩  "
            f"tool_messages={len(tool_indices)}  "
            f"keep={MICRO_COMPACT_KEEP}  "
            f"omit={len(omit_indices)}"
        )
        for idx in omit_indices:
            msg = messages[idx]
            if msg.content != OMITTED_PLACEHOLDER:
                msg.content = OMITTED_PLACEHOLDER

        return messages

    def estimate_context_size(self, messages: list[Any]) -> int:
        total = 0
        for msg in messages:
            content = getattr(msg, "content", "") or ""
            total += len(str(content))
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    fn = getattr(tc, "function", None)
                    if fn:
                        total += len(getattr(fn, "name", "") or "")
                        total += len(getattr(fn, "arguments", "") or "")
        return total

    def _messages_to_text(self, messages: list[Any]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "") or ""
            if not content.strip():
                continue
            lines.append(f"[{role}]\n{content[:4000]}")
        return "\n\n".join(lines[-30:])

    def compact_history(
        self,
        messages: list[Any],
        *,
        llm: Any,
        state_manager: "AgentStateManager",
    ) -> list[Any]:
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        original_system = system_messages[0] if system_messages else None

        todo_render = state_manager.render_todo()
        recent_files = list(self.state.recent_files)
        conversation_text = self._messages_to_text(messages)

        user_prompt = get_compact_user_prompt(conversation_text, todo_render, recent_files)

        try:
            summary_msg = llm.think(
                UserMessage(content=f"{COMPACT_SYSTEM_PROMPT}\n\n{user_prompt}")
            )
            summary = (summary_msg.content or "").strip()
        except Exception as exc:
            _log.warn(f"LLM 摘要压缩失败，使用 fallback  {exc}")
            summary = (
                f"Goal and progress preserved from {len(messages)} messages. "
                f"Todo:\n{todo_render}\nRecent files: {', '.join(recent_files) or 'none'}"
            )

        self.mark_compacted(summary)

        compact_notice = (
            "This conversation was compacted for continuity (s06).\n\n"
            f"{summary}\n\n"
            f"Current todo plan:\n{todo_render}\n\n"
            f"Recent files: {', '.join(recent_files) if recent_files else '(none)'}"
        )

        new_history: list[Any] = []
        if original_system:
            new_history.append(original_system)
        new_history.append(SystemMessage(content=compact_notice))

        _log.info(f"完整上下文压缩完成  compact_count={self.state.compact_count}")
        return new_history

    def prepare_context(
        self,
        messages: list[Any],
        *,
        llm: Any | None = None,
        state_manager: "AgentStateManager | None" = None,
        enable_full_compact: bool = True,
    ) -> list[Any]:
        """Run Layer 3 (if needed) then Layer 2 before each LLM call."""
        if (
            enable_full_compact
            and state_manager is not None
            and llm is not None
        ):
            should_compact = self.consume_compact_request()
            if not should_compact:
                should_compact = self.estimate_context_size(messages) > CONTEXT_LIMIT_CHARS

            if should_compact:
                messages = self.compact_history(
                    messages, llm=llm, state_manager=state_manager
                )

        return self.micro_compact(messages)
