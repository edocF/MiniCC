"""Project Intake Tool。"""
from pydantic import BaseModel
from MiniCC.tools.base_tool import BaseTool

# 自动注册到全局 Registry
from MiniCC.tools.tool_registry import register_tool


class IntakeArgs(BaseModel):
    project_root: str


class ProjectIntakeTool(BaseTool):
    name = "project_intake"
    description = "Inspect the Java project structure and return profile."
    args_schema = IntakeArgs

    def execute(self, project_root: str) -> dict:
        return {"project_root": project_root, "type": "maven_stub", "status": "intaked"}


# 模块加载时自动注册
register_tool(ProjectIntakeTool())
