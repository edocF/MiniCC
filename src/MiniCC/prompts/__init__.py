"""Prompt 管理模块 - 集中管理所有 LLM Prompt 模板。"""

from .react_prompts import REACT_AGENT_SYSTEM_PROMPT
from .planner_prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_PROMPT_TEMPLATE,
    get_planner_user_prompt,
)

__all__ = [
    "REACT_AGENT_SYSTEM_PROMPT",
    "PLANNER_SYSTEM_PROMPT",
    "PLANNER_USER_PROMPT_TEMPLATE",
    "get_planner_user_prompt",
]
