"""核心模块包。

避免在包导入时触发重型依赖链导致循环导入。
请按需从子模块导入：
- MiniCC.core.agent
- MiniCC.core.llm
- MiniCC.core.message
"""

__all__: list[str] = []

