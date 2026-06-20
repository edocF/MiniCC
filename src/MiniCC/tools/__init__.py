"""Tool 包：所有功能封装为 Tool，供 ReActAgent 使用。

Concrete tool modules may register themselves as import side effects. Keep the
package imports below explicit so the legacy import surface remains clear.
"""

from .base_tool import BaseTool
from .tool_registry import ToolRegistry, get_global_registry, register_tool
from . import filesystem_tool
from . import plan_tool
from . import executor  # triggers registration of executor (real cmdline runner)
from . import task_tool  # keeps generic TaskTool import surface; no auto registration
from . import visual_script_tool  # triggers registration of story/script sub-agent tool
from . import visual_storyboard_tool  # triggers registration of storyboard sub-agent tool
from . import todo_tool  # triggers registration of todo delegation tool
from . import compact_tool  # triggers registration of context compact tool

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "get_global_registry",
    "register_tool",
]

