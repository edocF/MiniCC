"""CommandRunner - Safe subprocess execution based on docs/03-execution-engine.md.

Implements secure cmdline execution with whitelist, timeout, shell=False,
output capture, and workspace cwd restriction. Matches mainstream
CodeAgent patterns (controlled subprocess before full Docker sandbox).
"""
import subprocess
import time
from pathlib import Path
from typing import List

from MiniCC.tools.executor.command_spec import CommandSpec, ExecutionResult


class CommandRunner:
    """Safe command executor following execution engine design."""

    # 仅保留真正能稳定执行的可执行文件。
    # 文件系统类操作（ls/dir/cat/grep/echo）请使用专用 Tool：
    # list_dir / read_file / glob / grep / write_file。
    ALLOWED_COMMANDS = {
        "python", "python3", "python.exe",
        "mvn", "mvnw", "mvnw.cmd",
        "gradle", "gradlew", "gradlew.bat",
        "java",
    }

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()

    def _check_command(self, spec: CommandSpec) -> str | None:
        """白名单校验。返回 None 表示通过，否则返回拒绝原因（用于 stderr）。

        注意：因为底层使用 shell=False，参数中的 ';' '|' '>' 等字符没有 shell 语义，
        所以这里不再做参数级字符黑名单（之前会把 `python -c "a;b"` 这种合法 Python
        源码错误地拦下来）。
        """
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
        """Restrict cwd to within workspace root for security."""
        cwd_path = Path(cwd).resolve()
        if not str(cwd_path).startswith(str(self.workspace_root)):
            # Default to workspace root if outside
            return self.workspace_root
        return cwd_path

    def run(self, spec: CommandSpec) -> ExecutionResult:
        """Execute command safely and return structured result."""
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
                error="invalid_command"
            )

        cwd_path = self._validate_cwd(spec.cwd)
        start_time = time.time()

        try:
            # Use shell=False for security (matches doc recommendation)
            result = subprocess.run(
                spec.argv,
                cwd=str(cwd_path),
                timeout=spec.timeout_seconds,
                capture_output=True,
                text=True,
                shell=False,
                env=None,  # Use default env for simplicity in first version
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
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
                error="timeout"
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
                error="tool_not_found"
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
                error="process_error"
            )
