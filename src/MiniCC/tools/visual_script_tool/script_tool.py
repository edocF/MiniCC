"""Visual Script Tool - 专业编写数学可视化故事/讲解脚本的 SubAgent."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from MiniCC.core.llm import LLM
from MiniCC.core.logger import get_logger
from MiniCC.prompts.manim_skill_prompts import MANIM_CAPABILITY_PROMPT
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import register_tool
from MiniCC.tools.visual_record import save_visual_script_record

_log = get_logger("ScriptTool")


SCRIPT_SYSTEM_PROMPT = """你是 MiniCC 的专业数学可视化故事/讲解脚本 SubAgent。

你的唯一职责是：在分镜之前，把数学题改写成一个适合可视化表达的好故事/讲解脚本。
你不写代码、不制定镜头分镜、不调用工具。

你必须关注：
- 题目中的对象、变量、数量关系和变化过程。
- 学生理解这道题时最容易卡住的地方。
- 如何把抽象数学关系转成自然、直观、有画面感的故事。
- 哪些角色、物体、事件或场景能承载数学量。
- 每一段讲解台词要如何推动学生理解。

脚本应服务于后续分镜 Agent：
- 给出清晰的角色/对象和数学映射。
- 给出讲解顺序和关键数学节拍。
- 给出每段建议画面动作，但不要细化到镜头级分镜。

直接用自然语言输出脚本。可以有小标题、旁白、角色/场景说明和关键数学节拍。
不要输出 JSON，不要写代码，不要写 Markdown 代码块。

如果后续可能选择 Manim，请遵守下面的 Manim 能力边界：
{manim_capability}
"""


class VisualScriptArgs(BaseModel):
    problem: str = Field(..., description="原始数学题")
    problem_type: str = Field("", description="主 Agent 对题型的初步判断，可为空")
    math_focus: str = Field("", description="主 Agent 认为最关键的数学关系，可为空")
    tone: str = Field(
        "课堂讲解",
        description="脚本风格，例如课堂讲解、生活故事、探索式、轻松活泼",
    )
    context: str = Field("", description="必要的补充上下文，保持简洁")


class VisualScriptTool(BaseTool):
    name = "visual_script"
    description = (
        "Use a specialized story/script SubAgent to turn a math problem into a "
        "clear, vivid, free-form visual narrative script before storyboard planning."
    )
    args_schema = VisualScriptArgs

    def __init__(self):
        super().__init__()
        self.llm = LLM(temperature=0.3)
        self.system_prompt = SCRIPT_SYSTEM_PROMPT.format(
            manim_capability=MANIM_CAPABILITY_PROMPT
        )

    def execute(
        self,
        problem: str,
        problem_type: str = "",
        math_focus: str = "",
        tone: str = "课堂讲解",
        context: str = "",
    ) -> dict[str, Any]:
        """Generate a free-form visual story/script."""
        workflow = [
            "读取原题、题型初判、核心数学关系和脚本风格。",
            "识别学生理解题目时最容易卡住的抽象关系。",
            "把抽象关系转成角色、场景、冲突和讲解顺序。",
            "输出自然语言故事/讲解脚本，供分镜 Agent 继续拆分。",
            "将脚本记录写入 outputs/reports，供 Coding Agent 查看。",
        ]
        user_prompt = (
            f"原题：\n{problem}\n\n"
            f"题型初判：{problem_type or '未提供'}\n"
            f"核心数学关系：{math_focus or '未提供'}\n"
            f"脚本风格：{tone}\n"
            f"补充上下文：\n{context or '无'}\n\n"
            "请先为这道题写一个数学可视化故事/讲解脚本。要求自然、清楚、有画面感，方便后续分镜 Agent 继续拆分镜头。"
        )

        try:
            response = self.llm._client.chat.completions.create(
                model=self.llm.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=self.llm.max_tokens,
            )
            if hasattr(self.llm, "_record_token_usage"):
                self.llm._record_token_usage(response)

            script_text = (response.choices[0].message.content or "").strip()
            record_path = save_visual_script_record(
                problem=problem,
                problem_type=problem_type,
                math_focus=math_focus,
                tone=tone,
                context=context,
                script=script_text,
                workflow=workflow,
            )
            _log.success(f"脚本生成完成  chars={len(script_text)}  record={record_path}")
            return {
                "status": "success",
                "script": script_text,
                "record_path": record_path,
                "workflow": workflow,
                "errors": [],
            }
        except Exception as exc:
            _log.error(f"脚本生成失败: {exc}")
            return {
                "status": "failed",
                "script": None,
                "record_path": None,
                "workflow": workflow,
                "errors": [str(exc)],
            }


register_tool(VisualScriptTool())
