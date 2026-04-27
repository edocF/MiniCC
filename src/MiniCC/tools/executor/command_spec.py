"""Command specification models based on docs/03-execution-engine.md."""
from pydantic import BaseModel, Field
from typing import Dict, List


class CommandSpec(BaseModel):
    """Structured command specification for safe execution.
    
    Follows the design in 03-execution-engine.md.
    Uses argv list (shell=False) for security.
    """
    argv: List[str] = Field(..., description="Command and arguments as list (e.g. ['python', '-c', 'print(1)'])")
    cwd: str = Field(..., description="Working directory for the command")
    timeout_seconds: int = Field(300, ge=1, le=600, description="Timeout in seconds (default 300s)")
    env_overrides: Dict[str, str] = Field(default_factory=dict, description="Environment variable overrides")
    kind: str = Field("diagnostic", description="Command type: diagnostic, python_exec, test_run, etc.")


class ExecutionResult(BaseModel):
    """Structured result from command execution."""
    success: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_ms: int | None = None
    command: List[str]
    cwd: str
    error: str | None = None
