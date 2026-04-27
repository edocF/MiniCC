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

MODE_TOOL_NAMES: dict[str, FrozenSet[str]] = {
    PLAN_MODE: frozenset(
        {
            "planner",
            "exit_plan_mode",
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
            "executor",
        }
    ),
}


def normalize_mode(mode: str) -> str:
    """Return a supported runtime mode, falling back to active mode."""
    return mode if mode in SUPPORTED_MODES else ACTIVE_MODE


def get_allowed_tool_names(mode: str) -> FrozenSet[str]:
    """Return the tool names exposed for the given runtime mode."""
    return MODE_TOOL_NAMES[normalize_mode(mode)]
