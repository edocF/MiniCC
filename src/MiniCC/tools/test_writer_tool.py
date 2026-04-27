"""Test Writer Tool。"""
from pydantic import BaseModel
from MiniCC.tools.base_tool import BaseTool

# 自动注册到全局 Registry
from MiniCC.tools.tool_registry import register_tool


class WriterArgs(BaseModel):
    spec: dict
    context: dict


class TestWriterTool(BaseTool):
    name = "test_writer"
    description = "Generate JUnit test code based on spec and context."
    args_schema = WriterArgs

    def execute(self, spec: dict, context: dict) -> str:
        return f"// Generated test for {spec.get('target', 'unknown')}\\nclass Test {{}}"


# 模块加载时自动注册
register_tool(TestWriterTool())
