"""Planner Tool 相关的 Prompt 模板。"""

# Planner Tool 系统提示
PLANNER_SYSTEM_PROMPT = """You are an expert universal planner capable of creating high-quality plans for ANY complex task (software development, travel planning, business strategy, research projects, event organization, personal goals, product launch, etc.).

You MUST output a SINGLE valid JSON object that EXACTLY matches the JSON Schema provided.
Do not add any extra text, explanation, markdown, code blocks, or comments.
Output ONLY the JSON object.

Here is an example of the exact format you must follow:

{
  "goal": "Build user authentication system",
  "steps": [
    {
      "id": 1,
      "action": "Design login API endpoint",
      "tool_to_use": "read",
      "expected_output": "API specification document",
      "acceptance_criteria": "Must support JWT and OAuth2"
    },
    {
      "id": 2,
      "action": "Implement unit tests for auth logic",
      "tool_to_use": "executor",
      "expected_output": "Passing test suite",
      "acceptance_criteria": "Coverage > 85%"
    }
  ],
  "dependencies": {
    "1": [],
    "2": [1]
  },
  "acceptance_criteria": [
    "All security best practices followed",
    "Rate limiting implemented",
    "Comprehensive test coverage"
  ],
  "estimated_steps": 5,
  "created_in_plan_mode": true
}"""


def get_planner_user_prompt(goal: str, context_summary: str) -> str:
    """生成 Planner Tool 的用户提示。
    
    Args:
        goal: 任务目标
        context_summary: 来自只读工具分析的上下文摘要
        
    Returns:
        格式化的用户提示字符串
    """
    return f"""Goal: {goal}

Context from previous readonly tool analysis (use this to make the plan realistic and specific):
{context_summary}

Now generate a high-quality, realistic, and actionable structured plan for this goal.
Make the steps practical and appropriate for the domain.
Ensure all fields are filled meaningfully and the JSON exactly matches the schema."""


# 模板字符串版本（供参考）
PLANNER_USER_PROMPT_TEMPLATE = """Goal: {goal}

Context from previous readonly tool analysis (use this to make the plan realistic and specific):
{context_summary}

Now generate a high-quality, realistic, and actionable structured plan for this goal.
Make the steps practical and appropriate for the domain.
Ensure all fields are filled meaningfully and the JSON exactly matches the schema."""
