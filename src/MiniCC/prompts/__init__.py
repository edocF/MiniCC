"""Prompt 管理模块 - 集中管理所有 LLM Prompt 模板。"""

from .react_prompts import (
    REACT_AGENT_SYSTEM_PROMPT,
    VISUAL_MATH_STORYBOARD_JSON_SCHEMA,
)
from .planner_prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_PROMPT_TEMPLATE,
    get_planner_user_prompt,
)
from .sub_agent_prompts import SUB_AGENT_SYSTEM_PROMPT
from .compact_prompts import COMPACT_SYSTEM_PROMPT, get_compact_user_prompt
from .manim_skill_prompts import MANIM_CAPABILITY_PROMPT

__all__ = [
    "REACT_AGENT_SYSTEM_PROMPT",
    "VISUAL_MATH_STORYBOARD_JSON_SCHEMA",
    "PLANNER_SYSTEM_PROMPT",
    "PLANNER_USER_PROMPT_TEMPLATE",
    "get_planner_user_prompt",
    "SUB_AGENT_SYSTEM_PROMPT",
    "COMPACT_SYSTEM_PROMPT",
    "get_compact_user_prompt",
    "MANIM_CAPABILITY_PROMPT",
]
