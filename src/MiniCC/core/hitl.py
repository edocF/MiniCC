"""Human-in-the-Loop (HITL) approval layer.

在 ReActAgent 的工具调用入口前提供一道集中式审批，拦截：

- ``write_file``  ：一律审批
- ``edit_file``   ：一律审批
- ``delete_file`` ：一律审批
- ``executor``    ：仅当 argv 中包含写/删类关键词时审批（启发式）

交互风格沿用 Claude Code 的 ``y / n / a / A / d``：

- ``y`` 本次允许
- ``n`` 拒绝（拒绝消息会以 ``[HITL Rejected] ...`` 回灌给 LLM）
- ``a`` 本会话内允许该工具的所有调用
- ``A`` 本会话内允许该工具在此 key（path / argv）上的调用
- ``d`` 切换详细预览（diff / 完整源码）后再选

环境变量：

- ``MINICC_AUTO_APPROVE=1`` 全局跳过审批，用于 CI / 非交互环境，否则在
  无 stdin 的环境里 ``input()`` 会卡住。
"""
from __future__ import annotations

import difflib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from MiniCC.core.logger import (
    BOLD,
    BRIGHT_GREEN,
    BRIGHT_MAGENTA,
    BRIGHT_YELLOW,
    CYAN,
    DIM,
    RED,
    RESET,
    YELLOW,
    get_logger,
)

_log = get_logger("HITL")


# 受控工具集合（write_file/edit_file/delete_file 一律审批；executor 走启发式）
_GUARDED_TOOLS: frozenset[str] = frozenset(
    {"write_file", "edit_file", "delete_file", "executor"}
)

# executor argv 中匹配到这些关键词时认为是破坏性操作
_EXECUTOR_DESTRUCTIVE_KEYWORDS: tuple[str, ...] = (
    # 写
    "open(",
    ".write(",
    ".writelines(",
    "write_text(",
    "write_bytes(",
    "shutil.copy",
    "shutil.move",
    # 删
    "os.remove",
    "os.unlink",
    "unlink(",
    "rmdir(",
    "shutil.rmtree",
)

# diff/预览截断阈值
_DIFF_DEFAULT_LINES = 60
_DIFF_EXPAND_LINES = 500
_WRITE_PREVIEW_MAX_CHARS = int(os.getenv("MINICC_HITL_PREVIEW_CHARS", "8000"))
_WRITE_PREVIEW_EDGE_LINES = 30
_DELETE_PREVIEW_LINES = 5
_DELETE_EXPAND_LINES = 30
_EXECUTOR_CODE_DEFAULT = 80
_EXECUTOR_CODE_EXPAND = 500


# ==================== 数据类 ====================
@dataclass
class ApprovalDecision:
    """审批结果。``reason`` 在拒绝时会被 ReAct 主循环以
    ``[HITL Rejected] {reason}`` 形式作为 ToolMessage 回灌给 LLM。
    """

    approved: bool
    reason: str = ""


def _truthy_env(name: str) -> bool:
    val = os.getenv(name, "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


# ==================== 启发式 ====================
def _executor_is_destructive(argv: Any) -> tuple[bool, list[str]]:
    """检测 executor 的 argv 是否含写/删意图。返回 (是否危险, 命中关键词列表)。"""
    if not argv or not isinstance(argv, list):
        return False, []
    matched: list[str] = []
    for arg in argv:
        if not isinstance(arg, str):
            continue
        for kw in _EXECUTOR_DESTRUCTIVE_KEYWORDS:
            if kw in arg and kw not in matched:
                matched.append(kw)
    return (len(matched) > 0), matched


# ==================== 预览生成 ====================
def _truncate_lines(text: str, max_lines: int) -> str:
    """按行数截断，超出部分提示 [d] 展开。"""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    omitted = len(lines) - max_lines
    head = "\n".join(lines[:max_lines])
    return head + f"\n{DIM}... 还有 {omitted} 行省略 (按 [d] 展开){RESET}"


def _truncate_content_preview(content: str, expand: bool = False) -> str:
    """超大 content 只展示首尾片段，避免终端被刷屏。"""
    max_chars = _WRITE_PREVIEW_MAX_CHARS * 4 if expand else _WRITE_PREVIEW_MAX_CHARS
    if len(content) <= max_chars:
        return content
    lines = content.splitlines()
    if len(lines) <= _WRITE_PREVIEW_EDGE_LINES * 2:
        half = max_chars // 2
        return (
            content[:half]
            + f"\n{DIM}... 中间省略 {len(content) - max_chars} 字符 (共 {len(content)} 字符，按 [d] 展开) ...{RESET}\n"
            + content[-half:]
        )
    head = "\n".join(lines[:_WRITE_PREVIEW_EDGE_LINES])
    tail = "\n".join(lines[-_WRITE_PREVIEW_EDGE_LINES:])
    omitted = len(lines) - _WRITE_PREVIEW_EDGE_LINES * 2
    return (
        head
        + f"\n{DIM}... 中间省略 {omitted} 行 / {len(content)} 字符 (按 [d] 展开) ...{RESET}\n"
        + tail
    )


def _render_edit_preview(args: dict[str, Any], expand: bool = False) -> str:
    path_str = str(args.get("path", "<unknown>"))
    edit_type = args.get("edit_type", "?")
    try:
        from MiniCC.tools.filesystem_tool.filesystem_tools import preview_edit

        old_content, new_content = preview_edit(path_str, args)
    except Exception as exc:  # noqa: BLE001 - preview only
        return (
            f"{BOLD}edit_file{RESET}  {YELLOW}预览失败{RESET}  "
            f"{CYAN}{path_str}{RESET}\n{DIM}{exc}{RESET}"
        )

    target = Path(path_str)
    try:
        target_resolved = target.resolve()
    except Exception:
        target_resolved = target

    head = (
        f"{BOLD}edit_file{RESET}  {edit_type}  "
        f"{CYAN}{target_resolved}{RESET}\n"
        f"{DIM}old_size={len(old_content)}  new_size={len(new_content)} chars{RESET}"
    )
    if edit_type == "lines":
        head += (
            f"\n{DIM}lines {args.get('start_line')}-{args.get('end_line')}{RESET}"
        )

    max_lines = _DIFF_EXPAND_LINES if expand else _DIFF_DEFAULT_LINES
    diff_iter = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        fromfile=f"a/{target.name}",
        tofile=f"b/{target.name}",
        lineterm="",
    )
    diff_lines: list[str] = []
    for ln in diff_iter:
        if ln.startswith("+++") or ln.startswith("---"):
            diff_lines.append(f"{DIM}{ln}{RESET}")
        elif ln.startswith("+"):
            diff_lines.append(f"{BRIGHT_GREEN}{ln}{RESET}")
        elif ln.startswith("-"):
            diff_lines.append(f"{RED}{ln}{RESET}")
        elif ln.startswith("@@"):
            diff_lines.append(f"{BRIGHT_MAGENTA}{ln}{RESET}")
        else:
            diff_lines.append(ln)
    body = "\n".join(diff_lines) if diff_lines else f"{DIM}(无变化){RESET}"
    return head + "\n" + _truncate_lines(body, max_lines)


def _render_write_preview(args: dict[str, Any], expand: bool = False) -> str:
    path_str = str(args.get("path", "<unknown>"))
    new_content = args.get("content", "")
    if not isinstance(new_content, str):
        new_content = str(new_content)
    append = bool(args.get("append", False))

    target = Path(path_str)
    try:
        target_resolved = target.resolve()
    except Exception:
        target_resolved = target

    exists = target.exists() and target.is_file()
    old_content = ""
    if exists:
        try:
            old_content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 - 仅用于预览
            old_content = f"<读取旧文件失败: {e}>"

    if append and exists:
        diff_target = old_content + new_content
        action = "追加"
    else:
        diff_target = new_content
        action = "覆盖" if exists else "新建"

    head = (
        f"{BOLD}write_file{RESET}  {action}  "
        f"{CYAN}{target_resolved}{RESET}\n"
        f"{DIM}new_size={len(new_content)} chars  exists={exists}  append={append}{RESET}"
    )

    max_lines = _DIFF_EXPAND_LINES if expand else _DIFF_DEFAULT_LINES
    preview_content = _truncate_content_preview(new_content, expand=expand)

    if not exists:
        body_lines = [f"{BRIGHT_GREEN}+ {ln}{RESET}" for ln in preview_content.splitlines()]
        body = "\n".join(body_lines) if body_lines else f"{DIM}(空文件){RESET}"
        return head + "\n" + _truncate_lines(body, max_lines)

    preview_target = (
        (old_content + preview_content) if append and exists else preview_content
    )
    diff_iter = difflib.unified_diff(
        old_content.splitlines(),
        preview_target.splitlines(),
        fromfile=f"a/{target.name}",
        tofile=f"b/{target.name}",
        lineterm="",
    )
    diff_lines: list[str] = []
    for ln in diff_iter:
        if ln.startswith("+++") or ln.startswith("---"):
            diff_lines.append(f"{DIM}{ln}{RESET}")
        elif ln.startswith("+"):
            diff_lines.append(f"{BRIGHT_GREEN}{ln}{RESET}")
        elif ln.startswith("-"):
            diff_lines.append(f"{RED}{ln}{RESET}")
        elif ln.startswith("@@"):
            diff_lines.append(f"{BRIGHT_MAGENTA}{ln}{RESET}")
        else:
            diff_lines.append(ln)
    body = "\n".join(diff_lines) if diff_lines else f"{DIM}(无变化){RESET}"
    return head + "\n" + _truncate_lines(body, max_lines)


def _render_delete_preview(args: dict[str, Any], expand: bool = False) -> str:
    path_str = str(args.get("path", "<unknown>"))
    recursive = bool(args.get("recursive", False))
    target = Path(path_str)
    try:
        target_resolved = target.resolve()
    except Exception:
        target_resolved = target

    if not target.exists():
        return (
            f"{BOLD}delete_file{RESET}  {YELLOW}目标不存在{RESET}  "
            f"{CYAN}{target_resolved}{RESET}"
        )

    if target.is_file():
        size = target.stat().st_size
        head = (
            f"{BOLD}delete_file{RESET}  {RED}删除文件{RESET}  "
            f"{CYAN}{target_resolved}{RESET}\n"
            f"{DIM}size={size} bytes{RESET}"
        )
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return head + f"\n<无法读取预览: {e}>"
        max_lines = _DELETE_EXPAND_LINES if expand else _DELETE_PREVIEW_LINES
        return head + "\n" + _truncate_lines(text, max_lines)

    if target.is_dir():
        if not recursive:
            return (
                f"{BOLD}delete_file{RESET}  {RED}尝试删除目录但 recursive=false{RESET}\n"
                f"{CYAN}{target_resolved}{RESET}\n"
                f"{YELLOW}该工具会在执行时拒绝；如需递归删除请重新调用并传 recursive=true。{RESET}"
            )
        cap = _DELETE_EXPAND_LINES if expand else _DELETE_PREVIEW_LINES * 2
        items: list[str] = []
        total = 0
        for p in target.rglob("*"):
            total += 1
            if len(items) < cap:
                rel = p.relative_to(target)
                items.append(f"  - {rel}{'/' if p.is_dir() else ''}")
        head = (
            f"{BOLD}delete_file{RESET}  {RED}递归删除目录{RESET}  "
            f"{CYAN}{target_resolved}{RESET}\n"
            f"{DIM}entries={total}{RESET}"
        )
        body = "\n".join(items) if items else f"{DIM}(空目录){RESET}"
        if total > len(items):
            body += f"\n{DIM}... 还有 {total - len(items)} 项 (按 [d] 展开){RESET}"
        return head + "\n" + body

    return f"{BOLD}delete_file{RESET}  {YELLOW}未知类型{RESET}  {target_resolved}"


def _render_executor_preview(args: dict[str, Any], expand: bool = False) -> str:
    argv = args.get("command") or []
    cwd = args.get("cwd", ".")
    kind = args.get("kind", "diagnostic")
    is_destr, matched = _executor_is_destructive(argv)

    head_tag = "写/删意图" if is_destr else "diagnostic"
    head_color = YELLOW if is_destr else DIM
    head = (
        f"{BOLD}executor{RESET}  "
        f"{head_color}{head_tag}{RESET}  "
        f"{DIM}cwd={cwd}  kind={kind}{RESET}"
    )
    if matched:
        head += f"\n{DIM}命中关键词:{RESET} {', '.join(matched)}"

    lines: list[str] = []
    if isinstance(argv, list):
        first = argv[0] if argv else ""
        first_norm = (
            first.lower().split("\\")[-1].split("/")[-1] if isinstance(first, str) else ""
        )
        if (
            len(argv) >= 3
            and first_norm in {"python", "python3", "python.exe"}
            and argv[1] in {"-c", "-m"}
        ):
            lines.append(f"{BOLD}{argv[0]} {argv[1]}{RESET}")
            cap = _EXECUTOR_CODE_EXPAND if expand else _EXECUTOR_CODE_DEFAULT
            lines.append(_truncate_lines(str(argv[2]), cap))
            if len(argv) > 3:
                lines.append(f"{DIM}extra args:{RESET} {argv[3:]}")
        else:
            lines.append(f"argv = {argv}")
    else:
        lines.append(f"argv = {argv!r}")

    return head + "\n" + "\n".join(lines)


# ==================== 审批管理器 ====================
class ApprovalManager:
    """会话级 HITL 状态机。模块单例，跨多次 ``agent.run()`` 保持记忆。"""

    def __init__(self) -> None:
        self._allow_tool: set[str] = set()
        self._allow_tool_key: set[tuple[str, str]] = set()
        self._auto_approve_announced: bool = False

    # ---- 公共 API ----
    def requires_approval(self, tool_name: str, args: dict[str, Any]) -> bool:
        if tool_name not in _GUARDED_TOOLS:
            return False
        if tool_name == "executor":
            argv = args.get("command")
            is_destr, _ = _executor_is_destructive(argv)
            return is_destr
        return True

    def request(self, tool_name: str, args: dict[str, Any]) -> ApprovalDecision:
        # 1) 全局自动通过（CI / yolo）
        if _truthy_env("MINICC_AUTO_APPROVE"):
            if not self._auto_approve_announced:
                _log.warn("MINICC_AUTO_APPROVE 已开启，所有 HITL 提示将被自动通过")
                self._auto_approve_announced = True
            return ApprovalDecision(True, "auto_approve_env")

        # 2) 会话内放行整工具
        if tool_name in self._allow_tool:
            _log.info(f"会话内已允许 {tool_name}，自动通过")
            return ApprovalDecision(True, "session_allow_tool")

        # 3) 会话内放行此工具+key
        key = self._make_key(tool_name, args)
        if key and (tool_name, key) in self._allow_tool_key:
            _log.info(f"会话内已允许 {tool_name}@{key}，自动通过")
            return ApprovalDecision(True, "session_allow_tool_key")

        # 4) 走交互
        return self._prompt(tool_name, args, key)

    def reset_session(self) -> None:
        """清空会话级允许集合。可在每次 ``agent.run()`` 开头调用以保证安全。"""
        self._allow_tool.clear()
        self._allow_tool_key.clear()
        self._auto_approve_announced = False

    # ---- 内部 ----
    def _make_key(self, tool_name: str, args: dict[str, Any]) -> str:
        if tool_name in {"write_file", "edit_file", "delete_file"}:
            p = args.get("path")
            if not p:
                return ""
            try:
                return str(Path(str(p)).resolve())
            except Exception:
                return str(p)
        if tool_name == "executor":
            argv = args.get("command") or []
            if isinstance(argv, list):
                return repr(tuple(argv))
            return repr(argv)
        return ""

    def _build_preview(
        self, tool_name: str, args: dict[str, Any], expand: bool
    ) -> str:
        if tool_name == "write_file":
            return _render_write_preview(args, expand=expand)
        if tool_name == "edit_file":
            return _render_edit_preview(args, expand=expand)
        if tool_name == "delete_file":
            return _render_delete_preview(args, expand=expand)
        if tool_name == "executor":
            return _render_executor_preview(args, expand=expand)
        return f"<no preview for {tool_name}>"

    def _prompt(
        self, tool_name: str, args: dict[str, Any], key: str
    ) -> ApprovalDecision:
        expand = False
        while True:
            preview = self._build_preview(tool_name, args, expand=expand)
            self._render_banner(tool_name, key, preview)
            try:
                raw = input(f"{BOLD}choice [y/n/a/A/d] > {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                _log.warn("HITL 输入中断，按拒绝处理")
                return ApprovalDecision(False, "user_interrupt")

            # 大小写敏感：'a' / 'A' 含义不同
            if raw == "" or raw in {"y", "Y"}:
                return ApprovalDecision(True, "user_yes")
            if raw in {"n", "N"}:
                return ApprovalDecision(False, "用户拒绝执行此次调用")
            if raw == "a":
                self._allow_tool.add(tool_name)
                _log.info(f"本会话内将自动放行 {tool_name} 的所有调用")
                return ApprovalDecision(True, "session_allow_tool")
            if raw == "A":
                if key:
                    self._allow_tool_key.add((tool_name, key))
                    _log.info(f"本会话内将自动放行 {tool_name} 在 {key} 的调用")
                else:
                    self._allow_tool.add(tool_name)
                    _log.warn(
                        f"无法为 {tool_name} 提取 key，已退化为放行整个工具"
                    )
                return ApprovalDecision(True, "session_allow_tool_key")
            if raw in {"d", "D"}:
                expand = not expand
                _log.info("已切换至详细预览，请重新选择" if expand else "已收起详细预览")
                continue
            print(f"{YELLOW}无效选项: {raw!r}，请输入 y / n / a / A / d{RESET}")

    def _render_banner(self, tool_name: str, key: str, preview: str) -> None:
        bar = f"{DIM}{'─' * 12}{RESET}"
        title = f"{BOLD}{BRIGHT_YELLOW}[HITL 审批] {tool_name}{RESET}"
        key_line = f"{DIM}key={key or '<none>'}{RESET}"
        opts = (
            f"{DIM}[y]{RESET} 本次允许   "
            f"{DIM}[n]{RESET} 拒绝   "
            f"{DIM}[a]{RESET} 本会话允许该工具   "
            f"{DIM}[A]{RESET} 本会话允许该工具+此 key   "
            f"{DIM}[d]{RESET} 切换详细预览"
        )
        print()
        print(f"{bar} {title} {bar}")
        print(key_line)
        print(preview)
        print(opts)


# ==================== 全局单例 ====================
_global_manager = ApprovalManager()


def get_global_approval_manager() -> ApprovalManager:
    return _global_manager
