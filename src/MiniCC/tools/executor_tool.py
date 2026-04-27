"""ExecutorTool - Real command execution tool using CommandRunner.

Replaces previous stub. Supports structured CommandSpec for safe cmdline
execution (shell=False, whitelist, timeout, cwd restriction). Aligns
with docs/03-execution-engine.md and mainstream CodeAgent patterns.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List

from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.executor.command_spec import CommandSpec, ExecutionResult
from MiniCC.tools.executor.command_runner import CommandRunner
from MiniCC.tools.tool_registry import register_tool


class ExecutorArgs(BaseModel):
    """Args for executor tool. Supports both legacy test_code and new CommandSpec."""
    command: List[str] = Field(default_factory=list, description="Command as argv list")
    cwd: str = Field(".", description="Working directory (defaults to workspace root)")
    timeout_seconds: int = Field(60, ge=5, le=300, description="Timeout in seconds")
    kind: str = Field("diagnostic", description="Command kind for logging")


class ExecutorTool(BaseTool):
    """Safe command execution tool. Replaces stub with real subprocess via CommandRunner.

    Usage example (in LLM call):
    {
        "command": ["python", "-c", "print('Hello from executor')"],
        "cwd": ".",
        "timeout_seconds": 30,
        "kind": "python_exec"
    }
    """
    name = "executor"
    description = (
        "安全执行命令行（推荐使用 argv 列表）。支持 python, echo, dir 等诊断命令，"
        "内置白名单、timeout、cwd限制。shell=False，符合主流CodeAgent和03-execution-engine.md设计。"
        "PlanMode下用于验证计划，Active模式下用于执行测试/脚本。"
    )
    args_schema = ExecutorArgs

    def __init__(self):
        super().__init__()
        self.runner = CommandRunner()  # uses current working dir as workspace

    def execute(
        self,
        command: List[str] | None = None,
        cwd: str = ".",
        timeout_seconds: int = 60,
        kind: str = "diagnostic",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute command using secure CommandRunner."""
        if not command or not isinstance(command, list):
            # Legacy fallback for test_code (keep backward compat)
            test_code = kwargs.get("test_code", str(command or kwargs))
            if test_code and isinstance(test_code, str):
                command = ["python", "-c", test_code]

        if not command:
            return {
                "success": False,
                "error": "No command provided",
                "stdout": "",
                "stderr": "Missing command argv list",
            }

        spec = CommandSpec(
            argv=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            kind=kind,
        )

        result: ExecutionResult = self.runner.run(spec)

        return {
            "success": result.success,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "duration_ms": result.duration_ms,
            "command": result.command,
            "cwd": result.cwd,
            "error": result.error,
        }


# Auto register on import
register_tool(ExecutorTool())
