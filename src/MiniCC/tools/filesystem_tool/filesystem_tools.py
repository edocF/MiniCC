"""Filesystem tools for project structure exploration and code search.
Implements LS (list_dir), Glob, FileRead (read_file), and Grep tools as readonly utilities
for Plan mode. Follows the style of finish_tool.py and base_tool.py."""

import os
import re
import shutil
import glob as glob_module
from pathlib import Path
from typing import Any, List, Dict
from pydantic import BaseModel, Field

from MiniCC.core.logger import get_logger
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import register_tool

_log = get_logger("FsTools")


# ==================== List Directory (LS) ====================
class ListDirArgs(BaseModel):
    path: str = "."
    recursive: bool = False
    max_depth: int = 3


class ListDirTool(BaseTool):
    name = "list_dir"
    description = "List directory contents (LS). Supports recursive listing with depth limit. Ignores common hidden dirs like .git, __pycache__, node_modules. Returns formatted tree or list."
    args_schema = ListDirArgs

    def execute(self, path: str = ".", recursive: bool = False, max_depth: int = 3) -> str:
        """List files and directories."""
        try:
            root = Path(path).resolve()
            if not root.exists():
                return f"Error: Path '{path}' does not exist."

            if not root.is_dir():
                return f"Error: Path '{path}' is not a directory."

            ignored = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 'dist', 'build', '*.pyc'}

            def should_ignore(p: Path) -> bool:
                return any(ign in str(p) for ign in ignored) or p.name.startswith('.')

            if not recursive:
                items = []
                for item in sorted(root.iterdir()):
                    if should_ignore(item):
                        continue
                    prefix = "📁 " if item.is_dir() else "📄 "
                    items.append(f"{prefix}{item.name}")
                return f"Contents of {root}:\n" + "\n".join(items)

            # Recursive tree
            tree_lines = [f"Directory tree for: {root} (max_depth={max_depth})"]
            for current_path in root.rglob("*"):
                if should_ignore(current_path):
                    continue
                depth = len(current_path.relative_to(root).parts)
                if depth > max_depth:
                    continue
                indent = "  " * depth
                prefix = "📁 " if current_path.is_dir() else "📄 "
                rel_path = current_path.relative_to(root)
                tree_lines.append(f"{indent}{prefix}{rel_path}")
            return "\n".join(tree_lines[:50])  # limit output size
        except Exception as e:
            return f"ListDir error: {str(e)}"


# ==================== Glob ====================
class GlobArgs(BaseModel):
    pattern: str
    root_dir: str = "."


class GlobTool(BaseTool):
    name = "glob"
    description = "Search for files matching a glob pattern (similar to **/*.py). Returns list of matching file paths."
    args_schema = GlobArgs

    def execute(self, pattern: str, root_dir: str = ".") -> List[str]:
        """Find files using glob pattern."""
        try:
            root = Path(root_dir)
            if not root.exists():
                return [f"Error: root_dir '{root_dir}' does not exist."]

            matches = []
            for p in root.glob(pattern):
                if p.is_file():
                    matches.append(str(p.relative_to(root)))
            return sorted(matches) if matches else ["No matches found."]
        except Exception as e:
            return [f"Glob error: {str(e)}"]


# ==================== Read File ====================
class ReadFileArgs(BaseModel):
    path: str
    start_line: int = Field(
        1,
        ge=1,
        description="Start reading from this 1-based line number. Use this to continue reading later parts of large files.",
    )
    max_lines: int = Field(
        100,
        ge=1,
        le=200,
        description="Maximum number of lines to return. Output is always capped at 200 lines.",
    )


class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "Read file content from a chosen starting line. Use start_line to read later parts "
        "of large files and max_lines to control truncation. Output is always capped at 200 lines."
    )
    args_schema = ReadFileArgs

    def execute(
        self,
        path: str,
        start_line: int = 1,
        max_lines: int = 100,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Read specific lines from a file."""
        try:
            file_path = Path(path).resolve()
            if not file_path.exists():
                return f"Error: File '{path}' does not exist."
            if not file_path.is_file():
                return f"Error: '{path}' is not a file."

            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            # Backward compatibility for older tool calls that used offset/limit.
            if offset is not None:
                start_line = offset
            if limit is not None:
                max_lines = limit

            start_line = max(1, int(start_line))
            max_lines = min(200, max(1, int(max_lines)))
            start = min(len(lines), start_line - 1)
            end = min(len(lines), start + max_lines)
            selected_lines = lines[start:end]

            content = "".join(selected_lines)
            header = f"--- File: {file_path} (lines {start+1}-{end}, total {len(lines)} lines) ---\n"
            footer = f"\n--- End of file chunk (showing {len(selected_lines)} lines, max_lines={max_lines}) ---"
            if end < len(lines):
                footer += (
                    f"\n--- More content available. Next read: "
                    f"read_file(path={path!r}, start_line={end + 1}, max_lines={max_lines}) ---"
                )

            return header + content + footer
        except UnicodeDecodeError:
            return f"Error: Cannot read '{path}' as text file (binary?)."
        except Exception as e:
            return f"ReadFile error: {str(e)}"


# ==================== Grep ====================
class GrepArgs(BaseModel):
    pattern: str
    path: str = "."
    glob_pattern: str = "**/*"
    context: int = 2


class GrepTool(BaseTool):
    name = "grep"
    description = "Search for pattern (regex supported) in files. Returns matching lines with context, filename and line numbers. Similar to ripgrep but implemented with standard libs."
    args_schema = GrepArgs

    def execute(self, pattern: str, path: str = ".", glob_pattern: str = "**/*", context: int = 2) -> str:
        """Search code for pattern using regex."""
        try:
            root = Path(path)
            if not root.exists():
                return f"Error: Path '{path}' does not exist."

            regex = re.compile(pattern, re.IGNORECASE)
            results = []
            match_count = 0

            for file_path in root.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                if any(ign in str(file_path) for ign in ['.git', '__pycache__', '.pyc', 'node_modules']):
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()

                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            match_count += 1
                            rel_path = str(file_path.relative_to(root))
                            # Add context lines
                            start = max(0, i - 1 - context)
                            end = min(len(lines), i + context)
                            results.append(f"\n{rel_path}:{i}:")
                            for j in range(start, end):
                                prefix = ">" if j + 1 == i else " "
                                results.append(f"  {prefix}{j+1:4d} | {lines[j].rstrip()}")
                            if len(results) > 100:  # safety limit
                                results.append("\n... (truncated due to too many matches)")
                                break
                except Exception:
                    continue  # skip unreadable files

            if not results:
                return f"No matches found for pattern: '{pattern}' in {glob_pattern}"

            summary = f"Found {match_count} matches for '{pattern}' (context={context}):\n"
            return summary + "\n".join(results)
        except re.error as e:
            return f"Invalid regex pattern '{pattern}': {e}"
        except Exception as e:
            return f"Grep error: {str(e)}"


# ==================== Write File ====================
class WriteFileArgs(BaseModel):
    path: str = Field(..., description="目标文件路径（相对或绝对）")
    content: str = Field(..., description="要写入的完整内容")
    append: bool = Field(False, description="True 表示追加；False 覆盖（默认）")


class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "写入或创建文件。本工具的执行会触发 HITL 人工确认，用户会看到 unified diff 预览"
        "并通过 y/n/a/A/d 选择是否放行；模型无需自行传 confirm 参数。"
        "新文件会自动创建父目录；append=true 时为追加，否则覆盖。"
    )
    args_schema = WriteFileArgs

    def execute(
        self,
        path: str,
        content: str,
        append: bool = False,
        **_legacy: Any,  # 兼容旧调用传入的 confirm 等字段，统一忽略
    ) -> str:
        """写入文件。审批由 HITL 层在调用前完成；这里专注 IO。"""
        try:
            file_path = Path(path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = 'a' if append else 'w'
            with open(file_path, mode, encoding='utf-8') as f:
                f.write(content)

            action = "追加" if append else "写入"
            size = len(content)
            return (
                f"[成功] {action}完成\n"
                f"文件: {file_path}\n"
                f"大小: {size} 字符\n"
                f"模式: {'追加' if append else '覆盖'}\n"
                f"提示: 使用 read_file 工具可验证写入结果。"
            )
        except Exception as e:
            return f"WriteFile error: {str(e)}"


# ==================== Delete File ====================
class DeleteFileArgs(BaseModel):
    path: str = Field(..., description="待删除的文件或目录路径")
    recursive: bool = Field(
        False,
        description="删除目录时必须显式设为 true；删除单个文件时无需设置。",
    )


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = (
        "删除文件或目录。本工具的执行会触发 HITL 人工确认（路径预览 + 内容前若干行）。"
        "默认仅可删除单个文件；删除目录时必须显式传 recursive=true，否则会被拒绝。"
        "目标不存在时返回错误。优先使用此工具而不是 executor 间接删除文件。"
    )
    args_schema = DeleteFileArgs

    def execute(self, path: str, recursive: bool = False) -> str:
        try:
            target = Path(path).resolve()
            if not target.exists():
                return f"DeleteFile error: '{path}' 不存在"
            if target.is_file():
                target.unlink()
                return f"[成功] 已删除文件: {target}"
            if target.is_dir():
                if not recursive:
                    return (
                        f"DeleteFile error: '{path}' 是目录，需要 recursive=true 才能删除"
                    )
                shutil.rmtree(target)
                return f"[成功] 已递归删除目录: {target}"
            return f"DeleteFile error: '{path}' 既不是文件也不是目录"
        except Exception as e:
            return f"DeleteFile error: {e}"


# 模块加载时自动注册所有工具
register_tool(ListDirTool())
register_tool(GlobTool())
register_tool(ReadFileTool())
register_tool(GrepTool())
register_tool(WriteFileTool())
register_tool(DeleteFileTool())

_log.debug(
    "Filesystem tools 注册完成: list_dir / glob / read_file / grep / write_file / delete_file"
)
