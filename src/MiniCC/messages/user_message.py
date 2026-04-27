"""用户消息类，封装了用户消息的逻辑"""
from typing import Any

from MiniCC.core.message import Message


class UserMessage(Message):
    def __init__(self, content: str, metadata: dict[str, Any] | None = None):
        super().__init__("user", content, metadata)
    
    def to_openai_format(self) -> dict[str, Any]:
        return {
            "role": "user",
            "content": self.content,
        }

