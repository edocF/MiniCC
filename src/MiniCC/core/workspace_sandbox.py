"""Workspace path sandbox: confine all tool IO to an explicitly configured root."""
from __future__ import annotations

from pathlib import Path

_sandbox: "WorkspaceSandbox | None" = None


class WorkspaceNotConfiguredError(RuntimeError):
    """Raised when workspace sandbox has not been configured yet."""


class WorkspaceSandboxError(ValueError):
    """Raised when a path escapes the configured workspace."""

    def __init__(
        self,
        message: str,
        *,
        requested: str,
        resolved: Path,
        workspace: Path,
    ) -> None:
        self.requested = requested
        self.resolved = resolved
        self.workspace = workspace
        super().__init__(
            f"{message}\n"
            f"  requested: {requested}\n"
            f"  resolved: {resolved}\n"
            f"  workspace: {workspace}"
        )


class WorkspaceSandbox:
    """Resolve and validate paths within a single workspace root."""

    def __init__(self, root: str | Path) -> None:
        resolved = Path(root).resolve()
        if not resolved.exists():
            raise WorkspaceSandboxError(
                "Workspace root does not exist.",
                requested=str(root),
                resolved=resolved,
                workspace=resolved,
            )
        if not resolved.is_dir():
            raise WorkspaceSandboxError(
                "Workspace root is not a directory.",
                requested=str(root),
                resolved=resolved,
                workspace=resolved,
            )
        self.root = resolved

    def _candidate_path(self, user_path: str) -> Path:
        raw = Path(user_path)
        if raw.is_absolute():
            return raw.resolve()
        return (self.root / raw).resolve()

    def _ensure_inside(self, resolved: Path, requested: str) -> Path:
        if not resolved.is_relative_to(self.root):
            raise WorkspaceSandboxError(
                "Path escapes workspace.",
                requested=requested,
                resolved=resolved,
                workspace=self.root,
            )
        return resolved

    def resolve(self, user_path: str, *, must_exist: bool = False) -> Path:
        """Resolve user_path inside workspace. Raises WorkspaceSandboxError on escape."""
        requested = user_path
        resolved = self._candidate_path(user_path)
        self._ensure_inside(resolved, requested)

        if must_exist and not resolved.exists():
            raise WorkspaceSandboxError(
                "Path does not exist within workspace.",
                requested=requested,
                resolved=resolved,
                workspace=self.root,
            )
        return resolved

    def ensure_parent_writable(self, user_path: str) -> Path:
        """Resolve a file path for write; parent directory must stay inside workspace."""
        requested = user_path
        resolved = self._candidate_path(user_path)
        self._ensure_inside(resolved, requested)

        parent = resolved.parent
        self._ensure_inside(parent.resolve(), requested)

        return resolved


def configure_workspace(root: str | Path) -> WorkspaceSandbox:
    """Configure the global workspace sandbox singleton."""
    global _sandbox
    _sandbox = WorkspaceSandbox(root)
    return _sandbox


def get_workspace_sandbox() -> WorkspaceSandbox:
    """Return the configured sandbox or raise WorkspaceNotConfiguredError."""
    if _sandbox is None:
        raise WorkspaceNotConfiguredError(
            "Workspace not configured. Set MINICC_WORKSPACE_ROOT or pass "
            "workspace_root to ReActAgent(...)."
        )
    return _sandbox


def resolve_in_workspace(user_path: str, *, must_exist: bool = False) -> Path:
    """Convenience wrapper around get_workspace_sandbox().resolve()."""
    return get_workspace_sandbox().resolve(user_path, must_exist=must_exist)


def ensure_parent_writable_in_workspace(user_path: str) -> Path:
    """Convenience wrapper for write_file paths."""
    return get_workspace_sandbox().ensure_parent_writable(user_path)
