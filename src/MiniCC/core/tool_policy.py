"""Tool exposure policy for Agent runtime modes.

This module is the single source of truth for which tools are visible in each
runtime mode. Keeping the policy here avoids duplicated allowlists across the
state manager and registry.
"""
from __future__ import annotations

from typing import FrozenSet


ACTIVE_MODE = "active"
PLAN_MODE = "plan"
SUPPORTED_MODES: FrozenSet[str] = frozenset({ACTIVE_MODE, PLAN_MODE})

SUB_AGENT_BLOCKED_TOOLS: FrozenSet[str] = frozenset(
    {
        "task",
        "todo",
        "compact",
        "planner",
        "visual_script",
        "visual_storyboard",
        "enter_plan_mode",
        "exit_plan_mode",
    }
)

SUB_AGENT_DEFAULT_TOOLS: FrozenSet[str] = frozenset(
    {
        "list_dir",
        "glob",
        "read_file",
        "grep",
        "write_file",
        "edit_file",
        "delete_file",
        "executor",
    }
)

MODE_TOOL_NAMES: dict[str, FrozenSet[str]] = {
    PLAN_MODE: frozenset(
        {
            "planner",
            "exit_plan_mode",
            "todo",
            "compact",
            "list_dir",
            "glob",
            "read_file",
            "grep",
            "get_weather",
        }
    ),
    ACTIVE_MODE: frozenset(
        {
            "enter_plan_mode",
            "write_file",
            "edit_file",
            "delete_file",
            "executor",
            "visual_script",
            "visual_storyboard",
            "todo",
            "compact",
        }
    ),
}


def normalize_mode(mode: str) -> str:
    """Return a supported runtime mode, falling back to active mode."""
    return mode if mode in SUPPORTED_MODES else ACTIVE_MODE


def get_allowed_tool_names(mode: str) -> FrozenSet[str]:
    """Return the tool names exposed for the given runtime mode."""
    return MODE_TOOL_NAMES[normalize_mode(mode)]


def resolve_sub_agent_tools(requested: list[str] | None) -> frozenset[str]:
    """Resolve the tool allowlist for a SubAgent run.

    Uses SUB_AGENT_DEFAULT_TOOLS by default. If ``requested`` is provided,
    only tools within the default set are kept. Blocked tools are always removed.
    """
    base = SUB_AGENT_DEFAULT_TOOLS
    if requested is not None:
        unknown = [name for name in requested if name not in base]
        if unknown:
            raise ValueError(
                f"Unknown or disallowed sub-agent tools: {unknown}. "
                f"Allowed: {sorted(base)}"
            )
        base = frozenset(requested)

    return frozenset(name for name in base if name not in SUB_AGENT_BLOCKED_TOOLS)
