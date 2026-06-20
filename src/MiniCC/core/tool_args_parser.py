"""Safe parsing of LLM tool-call arguments with truncation detection."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from MiniCC.core.logger import get_logger

_log = get_logger("ToolArgsParser")

_PATH_RE = re.compile(r'"path"\s*:\s*"((?:\\.|[^"\\])*)"')


@dataclass
class ParseResult:
    """Result of parsing tool-call arguments."""

    args: dict | None = None
    error: str | None = None
    is_truncated: bool = False


def _extract_path_for_display(arguments_str: str) -> str | None:
    match = _PATH_RE.search(arguments_str)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


def _looks_truncated(arguments_str: str, exc: json.JSONDecodeError | None = None) -> bool:
    stripped = arguments_str.rstrip()
    if stripped and not stripped.endswith("}"):
        return True
    if exc is not None:
        msg = str(exc).lower()
        if "unterminated string" in msg or "expecting" in msg:
            return True
    return False


def _try_lightweight_repair(arguments_str: str) -> dict | None:
    fixed = re.sub(r'([^\\])"(\s*[\}\],])', r'\1\\" \2', arguments_str)
    fixed = re.sub(r"\n", r"\\n", fixed)
    try:
        return json.loads(fixed)
    except Exception:
        return None


def parse_tool_arguments(tool_name: str, arguments: str) -> ParseResult:
    """Parse tool-call arguments. Never falls back to dangerous placeholder paths."""
    arguments_str = arguments.strip()
    if not arguments_str:
        return ParseResult(
            error="arguments 为空，请重新生成合法的 JSON 参数。",
            is_truncated=False,
        )

    decode_error: json.JSONDecodeError | None = None
    try:
        return ParseResult(args=json.loads(arguments_str))
    except json.JSONDecodeError as exc:
        decode_error = exc

    is_truncated = _looks_truncated(arguments_str, decode_error)
    hinted_path = _extract_path_for_display(arguments_str)

    repaired = _try_lightweight_repair(arguments_str)
    if repaired is not None:
        _log.warn(f"工具 {tool_name} 的 arguments JSON 格式异常，已自动修复")
        return ParseResult(args=repaired)

    if is_truncated:
        path_hint = f"（目标路径可能为 {hinted_path!r}）" if hinted_path else ""
        _log.error(f"工具 {tool_name} 的 arguments 疑似被截断{path_hint}")
        return ParseResult(
            error=(
                "arguments JSON 被截断，请拆分为多次 write_file（append=true）"
                "或减小单次 content 体积后重试。"
                + (f" 目标路径可能为: {hinted_path}" if hinted_path else "")
            ),
            is_truncated=True,
        )

    _log.error(f"工具 {tool_name} 的 arguments JSON 格式无效")
    return ParseResult(
        error="arguments JSON 格式无效，请重新生成合法 JSON。",
        is_truncated=False,
    )
