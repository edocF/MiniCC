"""统一的日志模块，给整个 MiniCC 提供清晰、彩色、分级的输出。

使用方式：
    from MiniCC.core.logger import get_logger
    log = get_logger("StateManager")
    log.info("Hello")
    log.success("Done")
    log.tool_call("list_dir", {"path": "."})
    log.tool_result("list_dir", "...", duration_ms=12)

环境变量：
    MINICC_LOG_LEVEL=DEBUG|INFO|WARN|ERROR  控制最低输出等级（默认 INFO）
    MINICC_NO_COLOR=1                       关闭 ANSI 颜色
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

# ==================== ANSI 颜色 ====================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREY = "\033[90m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BRIGHT_GREEN = "\033[92m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_BLUE = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN = "\033[96m"


def _enable_windows_ansi() -> None:
    """在 Windows 终端启用 VT 序列，让 ANSI 颜色生效。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        STDOUT_HANDLE = -11
        handle = kernel32.GetStdHandle(STDOUT_HANDLE)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(
                handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            )
    except Exception:
        pass


def _force_utf8_stdout() -> None:
    """把 stdout / stderr 切换为 UTF-8，避免 Windows cp936 终端打印中文乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


_enable_windows_ansi()
_force_utf8_stdout()


def _color_enabled() -> bool:
    if os.getenv("MINICC_NO_COLOR"):
        return False
    if sys.platform == "win32":
        return True
    return sys.stdout.isatty()


def _c(text: str, color: str) -> str:
    """按需着色。"""
    if not _color_enabled():
        return text
    return f"{color}{text}{RESET}"


# ==================== 等级 ====================
# 自定义等级用于过滤；语义级别（OK/THINK/TOOL...）映射到这些等级
_LEVEL_RANK = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


def _resolve_min_level() -> int:
    raw = os.getenv("MINICC_LOG_LEVEL", "INFO").upper()
    return _LEVEL_RANK.get(raw, 20)


_MIN_LEVEL = _resolve_min_level()


# 语义标签 -> (显示文本, 颜色, 数值等级)
_TAGS: dict[str, tuple[str, str, int]] = {
    "DEBUG":  ("DEBUG", GREY,           10),
    "INFO":   ("INFO ", CYAN,           20),
    "OK":     ("OK   ", BRIGHT_GREEN,   20),
    "WARN":   ("WARN ", BRIGHT_YELLOW,  30),
    "ERROR":  ("ERROR", RED,            40),
    "THINK":  ("THINK", BRIGHT_BLUE,    20),
    "TOOL":   ("TOOL ", BRIGHT_MAGENTA, 20),
    "STATE":  ("STATE", YELLOW,         20),
    "ANSWER": ("ANSWR", BRIGHT_GREEN,   20),
}


# ==================== Logger ====================
class Logger:
    """轻量 logger：带时间戳、分级标签、模块名前缀。所有方法都打印到 stdout。"""

    NAME_WIDTH = 14

    def __init__(self, name: str):
        self.name = name

    # ---- 内部 ----
    def _emit(self, tag: str, message: str) -> None:
        label, color, rank = _TAGS.get(tag, _TAGS["INFO"])
        if rank < _MIN_LEVEL:
            return

        ts = datetime.now().strftime("%H:%M:%S")
        ts_part = _c(ts, GREY)
        tag_part = _c(f"[{label}]", color)
        name_part = _c(f"{self.name:<{self.NAME_WIDTH}}", DIM)
        head = f"{ts_part} {tag_part} {name_part} "
        # 缩进续行，对齐第一行
        indent = " " * (len(ts) + 1 + len(label) + 3 + self.NAME_WIDTH + 1)

        text = "" if message is None else str(message)
        lines = text.splitlines() or [""]
        sys.stdout.write(head + lines[0] + "\n")
        for line in lines[1:]:
            sys.stdout.write(indent + line + "\n")
        sys.stdout.flush()

    # ---- 通用等级 ----
    def debug(self, message: Any) -> None:
        self._emit("DEBUG", message)

    def info(self, message: Any) -> None:
        self._emit("INFO", message)

    def success(self, message: Any) -> None:
        self._emit("OK", message)

    def warn(self, message: Any) -> None:
        self._emit("WARN", message)

    warning = warn

    def error(self, message: Any) -> None:
        self._emit("ERROR", message)

    # ---- 语义化方法 ----
    def section(self, title: str) -> None:
        """输出一个醒目的分节标题（用于划分大阶段，如启动 / 最终结果）。"""
        bar = _c("─" * 12, DIM)
        t = _c(title, BOLD)
        sys.stdout.write(f"\n{bar}  {t}  {bar}\n\n")
        sys.stdout.flush()

    def thinking(self, text: str, max_chars: int = 800) -> None:
        """打印 LLM 的 thinking 段落，过长内容自动折叠。"""
        if not text:
            return
        text = text.strip()
        if len(text) > max_chars:
            text = text[:max_chars] + _c(f"\n... (省略 {len(text) - max_chars} 字符)", DIM)
        self._emit("THINK", text)

    def tool_call(self, name: str, args: dict | str | None = None) -> None:
        """打印工具调用：高亮名字 + 简短参数预览。"""
        try:
            args_str = json.dumps(args, ensure_ascii=False) if args is not None else ""
        except Exception:
            args_str = str(args)
        if len(args_str) > 240:
            args_str = args_str[:240] + "...(截断)"
        bold_name = _c(name, BOLD)
        suffix = f"  args={_c(args_str, DIM)}" if args_str else ""
        self._emit("TOOL", f"调用 {bold_name}{suffix}")

    def tool_result(
        self,
        name: str,
        result: Any,
        duration_ms: int | None = None,
        max_chars: int = 500,
    ) -> None:
        """打印工具返回值：长内容自动截断；失败用 error 级别。"""
        text = str(result)
        original_len = len(text)
        truncated = ""
        if original_len > max_chars:
            truncated = _c(f"  ... (截断 {original_len - max_chars} / {original_len} 字符)", DIM)
            text = text[:max_chars]

        meta_parts = [f"{original_len} 字符"]
        if duration_ms is not None:
            meta_parts.append(f"{duration_ms}ms")
        meta = _c(f"({', '.join(meta_parts)})", DIM)
        header = f"{_c(name, BOLD)} 返回 {meta}"

        # 简单错误启发：含 "error"/"失败"/"Failed" 走 warn 级别（仍可见但醒目）
        lower = text[:200].lower()
        is_error = any(k in lower for k in ("error", "failed", "exception", "拦截", "failed"))
        body = text + truncated
        msg = f"{header}\n{body}" if body.strip() else header
        if is_error:
            self._emit("WARN", msg)
        else:
            self._emit("OK", msg)

    def mode_change(self, old: str, new: str, reason: str = "") -> None:
        arrow = _c("→", BOLD)
        msg = f"mode {_c(old, DIM)} {arrow} {_c(new, BOLD)}"
        if reason:
            msg += _c(f"  reason={reason}", DIM)
        self._emit("STATE", msg)

    def final_answer(self, text: str) -> None:
        """高亮最终回答（粗体绿）。"""
        if not text:
            return
        self._emit("ANSWER", text.strip())

    def step(self, index: int, total: int | None = None) -> None:
        """打印一个 ReAct 步骤分隔。"""
        suffix = f"/{total}" if total else ""
        bar = _c("·" * 4, DIM)
        title = _c(f"Step {index}{suffix}", BOLD)
        sys.stdout.write(f"\n{bar} {title} {bar}\n")
        sys.stdout.flush()


# ==================== 工厂 ====================
_logger_cache: dict[str, Logger] = {}


def get_logger(name: str) -> Logger:
    """获取或创建命名 logger。同名复用同一实例。"""
    if name not in _logger_cache:
        _logger_cache[name] = Logger(name)
    return _logger_cache[name]


# 默认全局 logger
log = get_logger("MiniCC")
