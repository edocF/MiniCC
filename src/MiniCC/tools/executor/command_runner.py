"""CommandRunner - 安全命令执行 Tool（subprocess, shell=False）。

白名单校验、timeout、cwd 限制与结构化结果输出合并在同一 BaseTool 实现中。
"""
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from MiniCC.core.workspace_sandbox import (
    WorkspaceNotConfiguredError,
    WorkspaceSandboxError,
    resolve_in_workspace,
)
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.executor.command_spec import CommandSpec, ExecutionResult
from MiniCC.tools.tool_registry import register_tool


class CommandRunnerArgs(BaseModel):
    """executor 工具参数。兼容 legacy test_code 与 CommandSpec 风格调用。"""
    command: List[str] = Field(default_factory=list, description="Command as argv list")
    cwd: str = Field(".", description="Working directory (defaults to workspace root)")
    timeout_seconds: int = Field(60, ge=5, le=300, description="Timeout in seconds")
    kind: str = Field("diagnostic", description="Command kind for logging")


class CommandRunner(BaseTool):
    """安全命令执行：既是 Tool 入口，也负责 subprocess 调度。"""

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
    args_schema = CommandRunnerArgs

    # 文件系统类操作请使用专用 Tool：list_dir / read_file / glob / grep / write_file。
    ALLOWED_COMMANDS = {
        "python", "python3", "python.exe",
        "mvn", "mvnw", "mvnw.cmd",
        "gradle", "gradlew", "gradlew.bat",
        "java",
    }

    def execute(
        self,
        command: List[str] | None = None,
        cwd: str = ".",
        timeout_seconds: int = 60,
        kind: str = "diagnostic",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Tool 入口：解析参数并执行命令。"""
        if not command or not isinstance(command, list):
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
        return self._result_to_dict(self.run(spec))

    def run(self, spec: CommandSpec) -> ExecutionResult:
        """按 CommandSpec 执行命令，返回结构化结果。"""
        reject_reason = self._check_command(spec)
        if reject_reason is not None:
            return ExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr=reject_reason,
                timed_out=False,
                duration_ms=0,
                command=spec.argv,
                cwd=spec.cwd,
                error="invalid_command",
            )

        try:
            cwd_path = self._validate_cwd(spec.cwd)
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as exc:
            return ExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr=f"Sandbox error: {exc}",
                timed_out=False,
                duration_ms=0,
                command=spec.argv,
                cwd=spec.cwd,
                error="sandbox_violation",
            )

        start_time = time.time()

        try:
            env = {
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                **spec.env_overrides,
            }
            result = subprocess.run(
                spec.argv,
                cwd=str(cwd_path),
                timeout=spec.timeout_seconds,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=env,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=(result.stdout or "").strip(),
                stderr=(result.stderr or "").strip(),
                timed_out=False,
                duration_ms=duration_ms,
                command=spec.argv,
                cwd=str(cwd_path),
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr=f"Command timed out after {spec.timeout_seconds}s",
                timed_out=True,
                duration_ms=duration_ms,
                command=spec.argv,
                cwd=str(cwd_path),
                error="timeout",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr=f"Command not found: {spec.argv[0]}",
                timed_out=False,
                duration_ms=int((time.time() - start_time) * 1000),
                command=spec.argv,
                cwd=str(cwd_path),
                error="tool_not_found",
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr=str(e),
                timed_out=False,
                duration_ms=duration_ms,
                command=spec.argv,
                cwd=str(cwd_path),
                error="process_error",
            )

    def _check_command(self, spec: CommandSpec) -> str | None:
        """白名单校验。返回 None 表示通过，否则返回拒绝原因。"""
        if not spec.argv:
            return "Empty argv: 必须提供 argv 列表，例如 ['python', '-c', 'print(1)']"
        base_cmd = spec.argv[0].lower().split("\\")[-1].split("/")[-1]
        if base_cmd not in self.ALLOWED_COMMANDS:
            allowed = sorted(self.ALLOWED_COMMANDS)
            return (
                f"Command '{base_cmd}' 不在 executor 白名单内。"
                f"executor 仅用于运行 {allowed} 等可执行文件。"
                "若需要列目录/读文件/搜索，请改用 list_dir / read_file / glob / grep 工具。"
            )
        return None

    def _validate_cwd(self, cwd: str) -> Path:
        """将 cwd 限制在已配置的工作区根目录内。"""
        return resolve_in_workspace(cwd, must_exist=True)

    @staticmethod
    def _result_to_dict(result: ExecutionResult) -> Dict[str, Any]:
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


register_tool(CommandRunner())
