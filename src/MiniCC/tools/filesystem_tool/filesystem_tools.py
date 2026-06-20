"""Filesystem tools for project structure exploration and code search.
Implements LS (list_dir), Glob, FileRead (read_file), and Grep tools as readonly utilities
for Plan mode. Follows the style of finish_tool.py and base_tool.py."""

import os
import re
import shutil
import glob as glob_module
from pathlib import Path
from typing import Any, List, Dict, Literal
from pydantic import BaseModel, Field, model_validator

from MiniCC.core.logger import get_logger
from MiniCC.core.workspace_sandbox import (
    WorkspaceNotConfiguredError,
    WorkspaceSandboxError,
    ensure_parent_writable_in_workspace,
    resolve_in_workspace,
)
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
            root = resolve_in_workspace(path, must_exist=True)
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
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return f"Sandbox error: {e}"
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
            root = resolve_in_workspace(root_dir, must_exist=True)
            if not root.exists():
                return [f"Error: root_dir '{root_dir}' does not exist."]

            matches = []
            for p in root.glob(pattern):
                if p.is_file():
                    matches.append(str(p.relative_to(root)))
            return sorted(matches) if matches else ["No matches found."]
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return [f"Sandbox error: {e}"]
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
            file_path = resolve_in_workspace(path, must_exist=True)
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
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return f"Sandbox error: {e}"
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
            root = resolve_in_workspace(path, must_exist=True)
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
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return f"Sandbox error: {e}"
        except Exception as e:
            return f"Grep error: {str(e)}"


# ==================== Write File ====================
WRITE_FILE_MAX_CONTENT_CHARS = int(os.getenv("MINICC_WRITE_MAX_CHARS", "6000"))
_WRITE_JSON_ARGS_PREFIX = '{"path":'


class WriteFileArgs(BaseModel):
    path: str = Field(..., description="目标文件路径（相对或绝对，须在工作区内）")
    content: str = Field(
        ...,
        description=(
            "要写入的内容。单次建议不超过 6000 字符；大文件请拆分为多个文件"
            "（如 index.html + style.css + app.js），或先 write_file(append=false) 写骨架，"
            "再多次 write_file(append=true) 追加片段。"
        ),
    )
    append: bool = Field(False, description="True 表示追加；False 覆盖（默认）")


class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "写入或创建文件。本工具的执行会触发 HITL 人工确认，用户会看到 unified diff 预览"
        "并通过 y/n/a/A/d 选择是否放行；模型无需自行传 confirm 参数。"
        "新文件会自动创建父目录；append=true 时为追加，否则覆盖。"
        f"单次 content 不得超过 {WRITE_FILE_MAX_CONTENT_CHARS} 字符（覆盖模式）；"
        "超大 HTML/CSS/JS 必须拆文件或分 3-5 次 append=true 写入。"
        "修改已有文件中的几行请用 edit_file，不要用本工具覆盖全文件。"
    )
    args_schema = WriteFileArgs

    def _validate_content(self, path: str, content: str, append: bool) -> str | None:
        stripped = content.lstrip()
        if stripped.startswith(_WRITE_JSON_ARGS_PREFIX) and '"content"' in stripped[:200]:
            return (
                "WriteFile error: content 疑似为 tool arguments 的 JSON 原文，"
                "不是文件内容。请重新生成合法的 path 与 content 字段。"
            )
        if not append and len(content) > WRITE_FILE_MAX_CONTENT_CHARS:
            return (
                f"WriteFile error: 单次写入不得超过 {WRITE_FILE_MAX_CONTENT_CHARS} 字符"
                f"（当前 {len(content)}）。请拆分为多个文件，或使用 append=true 分块写入。"
            )
        return None

    def execute(
        self,
        path: str,
        content: str,
        append: bool = False,
        **_legacy: Any,  # 兼容旧调用传入的 confirm 等字段，统一忽略
    ) -> str:
        """写入文件。审批由 HITL 层在调用前完成；这里专注 IO。"""
        validation_error = self._validate_content(path, content, append)
        if validation_error:
            return validation_error
        try:
            file_path = ensure_parent_writable_in_workspace(path)
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
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return f"Sandbox error: {e}"
        except Exception as e:
            return f"WriteFile error: {str(e)}"


# ==================== Edit File (partial) ====================
EDIT_FILE_MAX_CHARS = int(os.getenv("MINICC_EDIT_MAX_CHARS", "6000"))


def _content_to_lines(content: str) -> list[str]:
    if not content:
        return []
    lines = content.splitlines(keepends=True)
    if content and not content.endswith(("\n", "\r\n")) and lines:
        if not lines[-1].endswith("\n"):
            return lines
    return lines


def apply_line_edit(
    lines: list[str],
    start_line: int,
    end_line: int,
    new_content: str,
) -> list[str]:
    """Replace lines [start_line, end_line] (1-based, inclusive) with new_content."""
    total = len(lines)
    if start_line < 1 or end_line < start_line:
        raise ValueError(
            f"无效行范围: start_line={start_line}, end_line={end_line}"
        )
    if end_line > total:
        raise ValueError(
            f"end_line={end_line} 超出文件总行数 {total}"
        )
    new_lines = _content_to_lines(new_content)
    start_idx = start_line - 1
    return lines[:start_idx] + new_lines + lines[end_line:]


def apply_search_replace(
    content: str,
    old_string: str,
    new_string: str,
    *,
    replace_all: bool = False,
) -> tuple[str, int]:
    """Replace old_string with new_string. Returns (new_content, replacement_count)."""
    if not old_string:
        raise ValueError("old_string 不能为空")
    count = content.count(old_string)
    if count == 0:
        raise ValueError("old_string 在文件中未找到，请先用 read_file 确认原文")
    if not replace_all and count > 1:
        raise ValueError(
            f"old_string 在文件中出现 {count} 次。"
            "请提供更多上下文使匹配唯一，或设置 replace_all=true。"
        )
    if replace_all:
        return content.replace(old_string, new_string), count
    return content.replace(old_string, new_string, 1), 1


def preview_edit(path: str, args: dict[str, Any]) -> tuple[str, str]:
    """Return (old_content, new_content) for HITL diff preview without writing."""
    file_path = resolve_in_workspace(path, must_exist=True)
    old_content = file_path.read_text(encoding="utf-8", errors="replace")
    edit_type = args.get("edit_type")
    if edit_type == "lines":
        lines = old_content.splitlines(keepends=True)
        if old_content and not old_content.endswith(("\n", "\r\n")) and lines:
            if lines and not lines[-1].endswith("\n"):
                pass
        new_lines = apply_line_edit(
            lines,
            int(args["start_line"]),
            int(args["end_line"]),
            str(args.get("new_content", "")),
        )
        new_content = "".join(new_lines)
    elif edit_type == "search_replace":
        new_content, _ = apply_search_replace(
            old_content,
            str(args["old_string"]),
            str(args.get("new_string", "")),
            replace_all=bool(args.get("replace_all", False)),
        )
    else:
        raise ValueError(f"未知 edit_type: {edit_type!r}")
    return old_content, new_content


class EditFileArgs(BaseModel):
    path: str = Field(..., description="目标文件路径（须在工作区内）")
    edit_type: Literal["lines", "search_replace"] = Field(
        ...,
        description=(
            "lines: 按行号替换（配合 read_file 的行号）；"
            "search_replace: 按精确文本片段替换"
        ),
    )
    start_line: int | None = Field(
        None,
        ge=1,
        description="lines 模式：起始行号（1-based，含）",
    )
    end_line: int | None = Field(
        None,
        ge=1,
        description="lines 模式：结束行号（1-based，含）",
    )
    new_content: str | None = Field(
        None,
        description="lines 模式：用于替换的新内容（可为多行，传空字符串表示删除该行范围）",
    )
    old_string: str | None = Field(
        None,
        description="search_replace 模式：要被替换的原文（须与文件内容完全一致）",
    )
    new_string: str | None = Field(
        None,
        description="search_replace 模式：替换后的新文本（可为空表示删除匹配片段）",
    )
    replace_all: bool = Field(
        False,
        description="search_replace 模式：是否替换所有匹配项（默认 false，要求唯一匹配）",
    )

    @model_validator(mode="after")
    def _validate_mode_fields(self) -> "EditFileArgs":
        if self.edit_type == "lines":
            if self.start_line is None or self.end_line is None or self.new_content is None:
                raise ValueError(
                    "lines 模式需要 start_line、end_line、new_content"
                )
            if self.end_line < self.start_line:
                raise ValueError("end_line 不能小于 start_line")
            if len(self.new_content) > EDIT_FILE_MAX_CHARS:
                raise ValueError(
                    f"new_content 不得超过 {EDIT_FILE_MAX_CHARS} 字符"
                )
        elif self.edit_type == "search_replace":
            if not self.old_string:
                raise ValueError("search_replace 模式需要 old_string")
            if self.new_string is None:
                raise ValueError("search_replace 模式需要 new_string")
            payload = len(self.old_string) + len(self.new_string)
            if payload > EDIT_FILE_MAX_CHARS:
                raise ValueError(
                    f"old_string + new_string 合计不得超过 {EDIT_FILE_MAX_CHARS} 字符"
                )
        return self


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "局部修改已有文件，无需重写整个文件。"
        "edit_type=lines：用 read_file 确认行号后，替换 start_line 到 end_line（含）之间的内容；"
        "edit_type=search_replace：将文件中唯一匹配的 old_string 替换为 new_string。"
        "修复几行错误、改一个 CSS 属性、改一个函数时优先使用本工具，而不是 write_file 覆盖全文件。"
        f"单次修改 payload 建议不超过 {EDIT_FILE_MAX_CHARS} 字符。"
    )
    args_schema = EditFileArgs

    def execute(
        self,
        path: str,
        edit_type: Literal["lines", "search_replace"],
        start_line: int | None = None,
        end_line: int | None = None,
        new_content: str | None = None,
        old_string: str | None = None,
        new_string: str | None = None,
        replace_all: bool = False,
        **_legacy: Any,
    ) -> str:
        try:
            EditFileArgs(
                path=path,
                edit_type=edit_type,
                start_line=start_line,
                end_line=end_line,
                new_content=new_content,
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
            )
        except ValueError as exc:
            return f"EditFile error: {exc}"

        try:
            file_path = resolve_in_workspace(path, must_exist=True)
            if not file_path.is_file():
                return f"EditFile error: '{path}' 不是文件"

            old_text = file_path.read_text(encoding="utf-8", errors="replace")

            if edit_type == "lines":
                lines = old_text.splitlines(keepends=True)
                if old_text and not old_text.endswith(("\n", "\r\n")) and lines:
                    if lines and not lines[-1].endswith("\n"):
                        pass
                new_lines = apply_line_edit(
                    lines, start_line, end_line, new_content or ""
                )
                new_text = "".join(new_lines)
                detail = (
                    f"行 {start_line}-{end_line} 已替换为 "
                    f"{len(_content_to_lines(new_content or ''))} 行"
                )
            else:
                new_text, count = apply_search_replace(
                    old_text,
                    old_string or "",
                    new_string or "",
                    replace_all=replace_all,
                )
                detail = f"search_replace 已应用 {count} 处"

            if new_text == old_text:
                return "EditFile error: 修改后内容与原文相同，未写入"

            file_path.write_text(new_text, encoding="utf-8")
            return (
                f"[成功] 局部修改完成\n"
                f"文件: {file_path}\n"
                f"{detail}\n"
                f"提示: 使用 read_file 验证修改结果。"
            )
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return f"Sandbox error: {e}"
        except ValueError as e:
            return f"EditFile error: {e}"
        except Exception as e:
            return f"EditFile error: {e}"


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
            target = resolve_in_workspace(path, must_exist=True)
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
        except (WorkspaceSandboxError, WorkspaceNotConfiguredError) as e:
            return f"Sandbox error: {e}"
        except Exception as e:
            return f"DeleteFile error: {e}"


# 模块加载时自动注册所有工具
register_tool(ListDirTool())
register_tool(GlobTool())
register_tool(ReadFileTool())
register_tool(GrepTool())
register_tool(WriteFileTool())
register_tool(EditFileTool())
register_tool(DeleteFileTool())

_log.debug(
    "Filesystem tools 注册完成: list_dir / glob / read_file / grep / "
    "write_file / edit_file / delete_file"
)
