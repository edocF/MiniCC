"""Visual Storyboard Tool - 专业制定数学可视化分镜的 SubAgent."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from MiniCC.core.llm import LLM
from MiniCC.core.logger import get_logger
from MiniCC.prompts.manim_skill_prompts import MANIM_CAPABILITY_PROMPT
from MiniCC.prompts.react_prompts import VISUAL_MATH_STORYBOARD_JSON_SCHEMA
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import register_tool
from MiniCC.tools.visual_record import save_visual_storyboard_record

_log = get_logger("StoryboardTool")


STORYBOARD_SYSTEM_PROMPT = """你是 MiniCC 的专业数学可视化分镜 SubAgent。

你的唯一职责是：根据数学题和上游故事/讲解脚本制定可实现的可视化分镜，不写代码、不执行工具、不输出散文报告。

你必须关注：
- 题目中的对象、变量、数量关系和变化过程。
- 上游脚本中的角色、叙事顺序、讲解台词和数学节拍。
- 学生最需要看见的数学关系。
- 应该使用 Canvas、JSXGraph 还是 Manim。
- 每一幕画面要出现什么对象、发生什么变化、显示什么公式或变量。
- 每个分镜必须包含多个 shots，让后续 Manim 代码能在每个分镜方法里写出足够丰富的内容。
- 需要哪些交互控件。

引擎选择规则：
- 应用题、生活场景动画、运动过程、数量累积，默认 engine=canvas。
- 函数图像、坐标系、解析几何、精确点线圆、参数滑块，优先 engine=jsxgraph。
- 课堂讲解动画、几何变换、分步骤推导视频、需要字幕/镜头节奏的演示，可以选择 engine=manim。

如果选择 Manim，分镜必须落在下面的 Manim 能力范围内：
{manim_capability}

只返回符合 JSON Schema 的 JSON 对象。不要 Markdown，不要代码块，不要解释文字。
"""


class VisualStoryboardArgs(BaseModel):
    problem: str = Field(..., description="原始数学题")
    problem_type: str = Field("", description="主 Agent 对题型的初步判断，可为空")
    math_focus: str = Field("", description="主 Agent 认为最关键的数学关系，可为空")
    script: str = Field(
        "",
        description="visual_script 工具返回的故事/讲解脚本文本",
    )
    preferred_engine: str = Field(
        "auto",
        description="auto/canvas/jsxgraph/manim；默认 auto，由分镜 SubAgent 判断",
    )
    context: str = Field("", description="必要的补充上下文，保持简洁")


class VisualStoryboardTool(BaseTool):
    name = "visual_storyboard"
    description = (
        "Use a specialized storyboard SubAgent to design a math visualization storyboard. "
        "It returns structured JSON constrained by VISUAL_MATH_STORYBOARD_JSON_SCHEMA. "
        "Call this before generating Canvas, JSXGraph, or Manim code."
    )
    args_schema = VisualStoryboardArgs

    def __init__(self):
        super().__init__()
        self.llm = LLM(temperature=0.2)
        self.system_prompt = STORYBOARD_SYSTEM_PROMPT.format(
            manim_capability=MANIM_CAPABILITY_PROMPT
        )

    def execute(
        self,
        problem: str,
        problem_type: str = "",
        math_focus: str = "",
        script: str = "",
        preferred_engine: str = "auto",
        context: str = "",
    ) -> dict[str, Any]:
        """Generate a schema-constrained storyboard plan."""
        workflow = [
            "读取原题、题型初判、核心数学关系和上游脚本文本。",
            "检查脚本中的角色、叙事顺序、讲解台词和数学节拍。",
            "选择最适合的可视化引擎：Canvas、JSXGraph 或 Manim。",
            "把脚本拆成结构化分镜：对象、变量、场景、多个 shots、动作、公式和控件。",
            "使用 JSON Schema 约束分镜输出。",
            "将脚本与分镜写入 outputs/reports，作为 Coding Agent 的实现依据。",
        ]
        script_text = script.strip() if isinstance(script, str) and script.strip() else "未提供"
        user_prompt = (
            f"原题：\n{problem}\n\n"
            f"题型初判：{problem_type or '未提供'}\n"
            f"核心数学关系：{math_focus or '未提供'}\n"
            f"上游故事/讲解脚本：\n{script_text}\n"
            f"偏好引擎：{preferred_engine}\n"
            f"补充上下文：\n{context or '无'}\n\n"
            "请基于原题和脚本制定数学可视化分镜，并严格返回符合 JSON Schema 的 JSON 对象。"
        )

        try:
            response = self.llm._client.chat.completions.create(
                model=self.llm.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=self.llm.max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "VisualMathStoryboard",
                        "schema": VISUAL_MATH_STORYBOARD_JSON_SCHEMA,
                        "strict": True,
                    },
                },
            )
            if hasattr(self.llm, "_record_token_usage"):
                self.llm._record_token_usage(response)

            content = response.choices[0].message.content or "{}"
            storyboard = json.loads(content)
            record_path = save_visual_storyboard_record(
                problem=problem,
                problem_type=problem_type,
                math_focus=math_focus,
                preferred_engine=preferred_engine,
                context=context,
                script=script_text,
                storyboard=storyboard,
                workflow=workflow,
            )
            _log.success(
                f"分镜生成完成  engine={storyboard.get('engine')}  "
                f"scenes={len(storyboard.get('scenes', []))}  record={record_path}"
            )
            return {
                "status": "success",
                "storyboard": storyboard,
                "record_path": record_path,
                "workflow": workflow,
                "errors": [],
            }
        except Exception as exc:
            _log.error(f"分镜生成失败: {exc}")
            return {
                "status": "failed",
                "storyboard": None,
                "record_path": None,
                "workflow": workflow,
                "errors": [str(exc)],
            }


register_tool(VisualStoryboardTool())
