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
        "运行可执行程序（subprocess, shell=False, 内置 timeout 与 cwd 限制）。\n"
        "用途：仅用于执行 Python 脚本与构建/测试工具，例如：\n"
        "  - python / python3 / python.exe  (运行脚本、单测、`python -c \"...\"`)\n"
        "  - java / mvn(w) / gradle(w)      (Java 构建与运行)\n"
        "白名单仅包含上述可执行文件，其他命令（ls / dir / cat / echo / grep 等）会被拒绝。\n"
        "command 必须是 argv 列表（例如 [\"python\", \"-c\", \"print(1)\"]），不要传 shell 字符串。\n"
        "注意：当 argv 中出现写/删类调用（open(...).write、os.remove、shutil.rmtree 等）时，"
        "本工具会触发 HITL 人工确认；如需写文件请优先用 write_file 工具，删文件用 delete_file 工具。"
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
