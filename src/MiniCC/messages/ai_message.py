"""AI消息类，封装了AI消息的逻辑"""
from typing import Any

from MiniCC.core.message import Message


class AIMessage(Message):
    def __init__(self, content: str, metadata: dict[str, Any] | None = None):
        super().__init__("assistant", content, metadata)
    
    def to_openai_format(self) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": self.content,
        }
    
