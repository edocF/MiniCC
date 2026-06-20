"""Persist large tool outputs to disk (s06 Layer 1)."""
from __future__ import annotations

import re
from pathlib import Path

from MiniCC.core.workspace_sandbox import get_workspace_sandbox

OUTPUT_DIR = Path(".task_outputs/tool-results")


def _sanitize_id(tool_call_id: str) -> str:
    safe = re.sub(r"[^\w\-]", "_", tool_call_id)
    return safe[:64] if safe else "unknown"


def save_tool_output(tool_call_id: str, content: str) -> str:
    """Save full tool output to disk. Returns relative path from workspace root."""
    root = get_workspace_sandbox().root
    out_dir = root / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_sanitize_id(tool_call_id)}.txt"
    file_path = out_dir / filename
    file_path.write_text(content, encoding="utf-8")

    return str(OUTPUT_DIR / filename).replace("\\", "/")
