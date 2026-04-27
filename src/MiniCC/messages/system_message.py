"""系统消息类，封装了系统消息的逻辑"""
from typing import Any

from MiniCC.core.message import Message


class SystemMessage(Message):
    def __init__(self, content: str, metadata: dict[str, Any] | None = None):
        super().__init__("system", content, metadata)
    
    def to_openai_format(self) -> dict[str, Any]:
        return {
            "role": "system",
            "content": self.content,
        }
