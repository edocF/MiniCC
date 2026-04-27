"""Tool related messages for ReAct architecture."""
from typing import Any

from MiniCC.core.message import Message


class ToolCallMessage(Message):
    """LLM 发出的 Tool Call 消息。"""

    def __init__(
        self,
        content: str = "",
        tool_calls: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__("assistant", content, metadata)
        self.tool_calls = tool_calls or []

    def to_openai_format(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": [tc.model_dump() if hasattr(tc, "model_dump") else vars(tc) for tc in self.tool_calls]
            if self.tool_calls
            else None,
        }


class ToolMessage(Message):
    """Tool 执行结果消息。"""

    def __init__(
        self,
        content: str,
        tool_call_id: str,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__("tool", content, metadata)
        self.tool_call_id = tool_call_id

    def to_openai_format(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_call_id": self.tool_call_id,
        }
