"""Analyzer Tool。"""
from pydantic import BaseModel
from MiniCC.tools.base_tool import BaseTool

# 自动注册到全局 Registry
from MiniCC.tools.tool_registry import register_tool


class AnalyzerArgs(BaseModel):
    execution_result: dict


class AnalyzerTool(BaseTool):
    name = "analyzer"
    description = "Analyze execution result and return structured report."
    args_schema = AnalyzerArgs

    def execute(self, execution_result: dict) -> dict:
        return {"success": execution_result.get("success", True), "failure_type": None}


# 模块加载时自动注册
register_tool(AnalyzerTool())
