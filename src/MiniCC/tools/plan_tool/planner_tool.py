"""Planner Tool - 使用 Qwen JSON Mode 动态生成结构化计划。"""
from pydantic import BaseModel, Field
from typing import List, Dict
from MiniCC.tools.base_tool import BaseTool
from MiniCC.core.llm import LLM
from MiniCC.prompts import PLANNER_SYSTEM_PROMPT, get_planner_user_prompt

# 自动注册到全局 Registry
from MiniCC.tools.tool_registry import register_tool


class PlannerArgs(BaseModel):
    goal: str = Field(..., description="The complex task or goal to plan for")
    context: str = Field("", description="Additional context from code analysis")


class PlanStep(BaseModel):
    id: int
    action: str
    tool_to_use: str
    expected_output: str
    acceptance_criteria: str


class StructuredPlan(BaseModel):
    goal: str
    steps: List[PlanStep]
    dependencies: Dict[str, List[int]]
    acceptance_criteria: List[str]
    estimated_steps: int
    created_in_plan_mode: bool = True


class PlannerTool(BaseTool):
    name = "planner"
    description = "用其他工具获取信息，在信息充足后调用该工具，在 PlanMode 下使用 Qwen JSON Mode 为复杂任务动态生成结构化计划。返回符合 StructuredPlan 的 JSON。"
    args_schema = PlannerArgs

    def __init__(self):
        super().__init__()
        self.llm = LLM()  # 使用项目中的 LLM 实例

    def execute(self, goal: str, context: str = "") -> dict:
        """使用 Qwen JSON Schema Mode 动态生成严格符合 StructuredPlan 的计划。
        context 来自前面只读工具收集的信息。"""
        context_summary = context[:1000] if context else "No additional context from readonly tools."
        print(f"[PlannerTool] Context summary: {context_summary}")
        # 使用 Pydantic 自动生成 JSON Schema
        schema = StructuredPlan.model_json_schema()

        # 从 prompts 模块导入 system_prompt
        system_prompt = PLANNER_SYSTEM_PROMPT

        # 使用 helper 函数生成 user_prompt
        user_prompt = get_planner_user_prompt(goal, context_summary)

        try:
            response = self.llm._client.chat.completions.create(
                model=self.llm.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "StructuredPlan",
                        "schema": schema,
                        "strict": True
                    }
                },
                temperature=0.2,
                max_tokens=2500,
            )

            json_str = response.choices[0].message.content.strip()
            plan = StructuredPlan.model_validate_json(json_str)
            result = plan.model_dump()

            print(f"[PlannerTool] Successfully generated JSON Schema validated plan for: {goal}")
            return result
        
        except Exception as e:
            print(f"[PlannerTool] JSON Schema validation failed: {e}. Using fallback template.")
            # Fallback to template when JSON Mode fails
            steps = [
                PlanStep(id=1, action=f"Analyze goal: {goal}", tool_to_use="read", expected_output="Project structure and key files", acceptance_criteria="Identify main modules and entry points"),
                PlanStep(id=2, action="Deep code analysis using readonly tools", tool_to_use="grep,semantic_search", expected_output="Core logic, dependencies and patterns", acceptance_criteria="Extract key functions, classes and data flows"),
                PlanStep(id=3, action="Create detailed structured test plan", tool_to_use="planner", expected_output="Complete plan document", acceptance_criteria="Clear steps with dependencies and acceptance criteria"),
                PlanStep(id=4, action="Implement according to the plan", tool_to_use="executor", expected_output="Working code and tests", acceptance_criteria="Passes linting and basic tests"),
            ]

            plan = StructuredPlan(
                goal=goal,
                steps=steps,
                dependencies={"1": [], "2": [1], "3": [1, 2], "4": [3]},
                acceptance_criteria=[
                    "Plan must be based on real code analysis from readonly tools",
                    "Each step must have clear tool and acceptance criteria",
                    "Final plan must be executable in the following execution phase"
                ],
                estimated_steps=len(steps),
            )
            return plan.model_dump()


# 模块加载时自动注册
register_tool(PlannerTool())

"""测试"""
if __name__ == "__main__":
    planner_tool = PlannerTool()
    result = planner_tool.execute(goal="请生成一个结构化计划", context="这是一个复杂任务：请分析当前天气，制定一个完整的旅行")
    print(result)
