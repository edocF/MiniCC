"""BaseTool 抽象类，所有 Tool 必须继承此类。"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

from pydantic import BaseModel


class BaseTool(ABC):
    """所有 Tool 的基类，用于 ReAct Agent 的 Tool Calling。"""

    name: str
    description: str
    args_schema: Type[BaseModel]

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """执行 Tool 并返回结果。"""
        pass

    def to_openai_tool(self) -> Dict[str, Any]:
        """转换为 OpenAI Tool Calling 格式。"""
        schema = self.args_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    def register_self(self, registry=None) -> None:
        """便捷方法：将自身注册到 Registry（默认全局）。"""
        # 延迟导入，避免 base_tool <-> tool_registry 循环导入
        from MiniCC.tools.tool_registry import get_global_registry

        if registry is None:
            registry = get_global_registry()
        registry.register(self)
