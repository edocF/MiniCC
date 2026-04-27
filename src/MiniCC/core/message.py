"""Message 抽象基类（ReAct 修订版）。具体消息类移至 messages/ 包下，避免循环导入。"""

from abc import ABC, abstractmethod
from typing import Any


class Message(ABC):
    """所有消息的抽象基类。"""

    def __init__(self, role: str, content: str, metadata: dict[str, Any] | None = None):
        self.role = role
        self.content = content
        self.metadata = metadata or {}

    @abstractmethod
    def to_openai_format(self) -> dict[str, Any]:
        pass


__all__ = ["Message"]

