"""Helpers for persisting visual math planning records."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from MiniCC.core.workspace_sandbox import get_workspace_sandbox
from MiniCC.prompts.manim_skill_prompts import MANIM_CAPABILITY_PROMPT

REPORT_DIR = Path("outputs/reports")


def _slug(text: str, fallback: str) -> str:
    value = re.sub(r"[^\w\-]+", "_", text.strip().lower(), flags=re.UNICODE)
    value = value.strip("_")
    return (value[:48] or fallback).replace("\\", "_").replace("/", "_")


def _report_path(prefix: str, problem_type: str = "") -> tuple[Path, str]:
    root = get_workspace_sandbox().root
    out_dir = root / REPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{_slug(problem_type, 'math')}_{stamp}.md"
    abs_path = out_dir / filename
    rel_path = str(REPORT_DIR / filename).replace("\\", "/")
    return abs_path, rel_path


def save_visual_script_record(
    *,
    problem: str,
    problem_type: str,
    math_focus: str,
    tone: str,
    context: str,
    script: str,
    workflow: list[str],
) -> str:
    """Persist the story/script result for later coding agents."""
    abs_path, rel_path = _report_path("visual_script", problem_type)
    content = (
        "# Visual Math Script Record\n\n"
        "## SubAgent Workflow\n"
        + "\n".join(f"- {step}" for step in workflow)
        + "\n\n## Problem\n"
        f"{problem}\n\n"
        "## Inputs\n"
        f"- Problem type: {problem_type or '未提供'}\n"
        f"- Math focus: {math_focus or '未提供'}\n"
        f"- Tone: {tone}\n"
        f"- Context: {context or '无'}\n\n"
        "## Script\n"
        f"{script}\n"
    )
    abs_path.write_text(content, encoding="utf-8")
    return rel_path


def save_visual_storyboard_record(
    *,
    problem: str,
    problem_type: str,
    math_focus: str,
    preferred_engine: str,
    context: str,
    script: str,
    storyboard: dict[str, Any],
    workflow: list[str],
) -> str:
    """Persist the final script + storyboard handoff record."""
    abs_path, rel_path = _report_path("visual_storyboard", problem_type)
    storyboard_json = json.dumps(storyboard, ensure_ascii=False, indent=2)
    content = (
        "# Visual Math Coding Handoff\n\n"
        "## SubAgent Workflow\n"
        + "\n".join(f"- {step}" for step in workflow)
        + "\n\n## Problem\n"
        f"{problem}\n\n"
        "## Inputs\n"
        f"- Problem type: {problem_type or '未提供'}\n"
        f"- Math focus: {math_focus or '未提供'}\n"
        f"- Preferred engine: {preferred_engine}\n"
        f"- Context: {context or '无'}\n\n"
        "## Script\n"
        f"{script or '未提供'}\n\n"
        "## Storyboard JSON\n"
        "```json\n"
        f"{storyboard_json}\n"
        "```\n\n"
        "## Coding Agent Notes\n"
        "- Read this file before generating visual code.\n"
        "- Follow the script narrative and storyboard scenes.\n"
        "- Keep generated artifacts in the engine-specific outputs directory.\n"
        "- Check generated code and repair with minimal changes if needed.\n"
        "- For Manim, use one Python file for one complete visualization.\n"
        "- For Manim, map each storyboard scene to one rich Scene method.\n"
        "- For Manim, place construct() at the end of the Scene class and use it only as a scheduler.\n"
        "- For Manim, implement each scene's shots as visible beats with captions, actions, formulas, and math checkpoints.\n"
        "\n## Manim Capability Skill\n"
        f"{MANIM_CAPABILITY_PROMPT}\n"
    )
    abs_path.write_text(content, encoding="utf-8")
    return rel_path
