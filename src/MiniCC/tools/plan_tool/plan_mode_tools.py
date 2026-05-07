"""Plan Mode control tools: EnterPlanModeTool and ExitPlanModeTool.
These tools allow the Agent to switch between PlanMode (readonly) and execution mode.
"""
from pydantic import BaseModel, Field
from MiniCC.core.logger import get_logger
from MiniCC.tools.base_tool import BaseTool
from MiniCC.tools.tool_registry import register_tool
from MiniCC.core.state_manager import get_global_state_manager

_log = get_logger("PlanMode")


class PlanModeArgs(BaseModel):
    reason: str = Field(..., description="Reason for entering or exiting PlanMode")


class EnterPlanModeTool(BaseTool):
    name = "enter_plan_mode"
    description = "进入 PlanMode (只读计划模式)。进入后只能使用只读工具进行分析和制定计划。适合复杂任务。"
    args_schema = PlanModeArgs

    def execute(self, reason: str) -> str:
        """进入 PlanMode。通过状态中心切换为 'plan' 模式。"""
        state_manager = get_global_state_manager()
        state_manager.set_mode("plan")
        _log.info(f"进入 PlanMode  reason={reason}")
        return f"已进入 PlanMode (只读)。原因: {reason}。现在只能使用只读工具生成结构化计划。"


class ExitPlanModeTool(BaseTool):
    name = "exit_plan_mode"
    description = "退出 PlanMode，恢复完整工具集。根据已制定的计划开始执行任务。"
    args_schema = PlanModeArgs

    def execute(self, reason: str) -> str:
        """退出 PlanMode。通过状态中心切换为 'active' 模式。"""
        state_manager = get_global_state_manager()
        state_manager.set_mode("active")
        _log.info(f"退出 PlanMode  reason={reason}")
        return f"已退出 PlanMode。原因: {reason}。现在将根据计划执行任务。"


# 模块加载时自动注册
register_tool(EnterPlanModeTool())
register_tool(ExitPlanModeTool())
