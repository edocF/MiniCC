"""Tool Registry 中心：集中管理所有 Tool，实现动态注册和解耦。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from MiniCC.core.tool_policy import get_allowed_tool_names

if TYPE_CHECKING:
    from MiniCC.tools.base_tool import BaseTool


class ToolRegistry:
    """Tool 注册中心，支持动态注册、查询和 OpenAI Schema 生成。"""

    def __init__(self) -> None:
        self._tools: Dict[str, "BaseTool"] = {}

    def register(self, tool: "BaseTool") -> None:
        """注册 Tool，按 name 唯一标识。"""
        if tool.name in self._tools:
            # 可选：打印警告或覆盖
            pass
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> "BaseTool":
        """按名称获取 Tool，不存在则抛出异常。"""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def get_all_tools(self) -> list["BaseTool"]:
        """返回所有已注册 Tool。"""
        return list(self._tools.values())

    def get_tools_for_mode(self, mode: str) -> list["BaseTool"]:
        """根据字符串 mode 返回对应工具集。"""
        all_tools = self.get_all_tools()
        allowed = get_allowed_tool_names(mode)
        return [t for t in all_tools if t.name.lower() in allowed]

    def to_openai_tools(self) -> list[dict]:
        """生成 OpenAI Tool Calling 所需的 schemas 列表。"""
        return [tool.to_openai_tool() for tool in self.get_all_tools()]

    def clear(self) -> None:
        """清空注册表（主要用于测试）。"""
        self._tools.clear()


# 全局单例 Registry
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """获取全局 Registry 单例。"""
    return _global_registry


def register_tool(tool: "BaseTool") -> None:
    """便捷函数：将 Tool 注册到全局 Registry。"""
    get_global_registry().register(tool)
