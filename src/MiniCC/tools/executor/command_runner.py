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

    # Allowed base commands (first element of argv). Matches doc whitelist.
    ALLOWED_COMMANDS = {
        "python", "python3", "python.exe",
        "mvn", "mvnw", "mvnw.cmd",
        "gradle", "gradlew", "gradlew.bat",
        "java", "echo", "dir", "ls", "cat"  # diagnostic helpers for this project
    }

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()

    def _is_safe_command(self, spec: CommandSpec) -> bool:
        """Basic whitelist validation per 03-execution-engine.md."""
        if not spec.argv:
            return False
        base_cmd = spec.argv[0].lower().split("\\")[-1].split("/")[-1]
        if base_cmd not in self.ALLOWED_COMMANDS:
            return False
        # Prevent dangerous patterns (no shell meta chars in args for first version)
        for arg in spec.argv[1:]:
            if any(danger in arg for danger in ["&&", "||", ";", ">", "<", "|", "&"]):
                return False
        return True

    def _validate_cwd(self, cwd: str) -> Path:
        """Restrict cwd to within workspace root for security."""
        cwd_path = Path(cwd).resolve()
        if not str(cwd_path).startswith(str(self.workspace_root)):
            # Default to workspace root if outside
            return self.workspace_root
        return cwd_path

    def run(self, spec: CommandSpec) -> ExecutionResult:
        """Execute command safely and return structured result."""
        if not self._is_safe_command(spec):
            return ExecutionResult(
                success=False,
                exit_code=None,
                stdout="",
                stderr="Command not allowed by whitelist",
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
