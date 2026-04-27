"""Filesystem tools for project structure exploration and code search.
Implements LS (list_dir), Glob, FileRead (read_file), and Grep tools as readonly utilities
for Plan mode. Follows the style of finish_tool.py and base_tool.py."""

import os
import re
import glob as glob_module
from pathlib import Path
from typing import Any, List, Dict
from pydantic import BaseModel

from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import register_tool


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
    offset: int = 1
    limit: int = 100


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read file content with optional line range (offset and limit). Useful for inspecting code without loading entire large files. Supports up to 200 lines by default."
    args_schema = ReadFileArgs

    def execute(self, path: str, offset: int = 1, limit: int = 100) -> str:
        """Read specific lines from a file."""
        try:
            file_path = Path(path).resolve()
            if not file_path.exists():
                return f"Error: File '{path}' does not exist."
            if not file_path.is_file():
                return f"Error: '{path}' is not a file."

            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

            start = max(0, offset - 1)
            end = min(len(lines), start + limit)
            selected_lines = lines[start:end]

            content = "".join(selected_lines)
            header = f"--- File: {file_path} (lines {start+1}-{end}, total {len(lines)} lines) ---\n"
            footer = f"\n--- End of file (showing {len(selected_lines)} lines) ---"

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


# ==================== Write File (安全写入) ====================
class WriteFileArgs(BaseModel):
    path: str
    content: str
    confirm: bool = True # 必须设为 True 才能实际写入，防止意外覆盖
    append: bool = False   # 如果为 True，则追加内容而不是覆盖


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "安全写入文件或创建新文件。必须设置 confirm=true 才能执行写入操作（防止意外覆盖重要文件）。支持 append 模式。新文件创建时会自动创建父目录。content 参数必须是完整的有效字符串。推荐用于写入完整代码。"
    args_schema = WriteFileArgs

    def execute(self, path: str, content: str, confirm: bool = False, append: bool = False) -> str:
        """安全写入文件。只有 confirm=True 时才实际执行写操作。"""
        if not confirm:
            return f"""[安全拦截] 写入操作已被阻止。
文件路径: {path}
要实际写入，请设置 confirm=true。
当前模式: {'追加' if append else '覆盖'}
建议: 仅在确认内容正确后使用 confirm=true。"""

        try:
            file_path = Path(path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = 'a' if append else 'w'
            with open(file_path, mode, encoding='utf-8') as f:
                f.write(content)

            action = "追加" if append else "写入"
            size = len(content)
            return f"""[成功] {action}完成
文件: {file_path}
大小: {size} 字符
模式: {'追加' if append else '覆盖'}
提示: 使用 read_file 工具可验证写入结果。"""
        except Exception as e:
            return f"WriteFile error: {str(e)}"


# 模块加载时自动注册所有工具
register_tool(ListDirTool())
register_tool(GlobTool())
register_tool(ReadFileTool())
register_tool(GrepTool())
register_tool(WriteFileTool())

print("Filesystem tools (list_dir, glob, read_file, grep, write_file) registered successfully.")
