"""ReAct Agent 相关的 Prompt 模板。"""

from MiniCC.prompts.manim_skill_prompts import MANIM_CAPABILITY_PROMPT


VISUAL_MATH_STORYBOARD_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "problem_type",
        "engine",
        "visual_goal",
        "objects",
        "variables",
        "scenes",
        "controls",
    ],
    "properties": {
        "problem_type": {
            "type": "string",
            "description": "题型，例如行程、水池、利润、函数图像、解析几何等。",
        },
        "engine": {
            "type": "string",
            "enum": ["canvas", "jsxgraph", "manim"],
            "description": "允许 Canvas、JSXGraph 或 Manim；应用题默认 canvas。",
        },
        "visual_goal": {
            "type": "string",
            "description": "这次可视化要帮助学生看懂的核心数学关系。",
        },
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "label", "role", "visual"],
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "role": {
                        "type": "string",
                        "description": "对象在题目中的作用。",
                    },
                    "visual": {
                        "type": "string",
                        "description": "对象在画面中的表现形式。",
                    },
                },
            },
        },
        "variables": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "meaning", "initial_value", "unit"],
                "properties": {
                    "name": {"type": "string"},
                    "meaning": {"type": "string"},
                    "initial_value": {"type": ["number", "string"]},
                    "unit": {"type": "string"},
                },
            },
        },
        "scenes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "id",
                    "title",
                    "description",
                    "actions",
                    "math_focus",
                    "display",
                    "shots",
                ],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {
                        "type": "string",
                        "description": "这一分镜的完整讲解目标和画面意图，不能只写一句空泛描述。",
                    },
                    "actions": {
                        "type": "array",
                        "minItems": 2,
                        "items": {"type": "string"},
                    },
                    "math_focus": {
                        "type": "string",
                        "description": "这一幕对应的数学关系或公式。",
                    },
                    "display": {
                        "type": "array",
                        "minItems": 2,
                        "items": {
                            "type": "string",
                            "description": "这一幕需要显示在画面上的标签、变量、公式或提示。",
                        },
                    },
                    "shots": {
                        "type": "array",
                        "minItems": 2,
                        "description": "这一分镜内部的镜头/讲解节拍；Manim 实现时应让每个 shot 都有可见动作和文字解释。",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "id",
                                "narration",
                                "visual_action",
                                "animation",
                                "math_checkpoint",
                                "duration_seconds",
                            ],
                            "properties": {
                                "id": {"type": "string"},
                                "narration": {
                                    "type": "string",
                                    "description": "这一镜头的旁白/字幕，必须直接帮助学生理解。",
                                },
                                "visual_action": {
                                    "type": "string",
                                    "description": "这一镜头画面上发生的具体变化。",
                                },
                                "animation": {
                                    "type": "string",
                                    "description": "建议使用的动画表达，例如 FadeIn、Transform、MoveAlongPath、Indicate、Create 等。",
                                },
                                "math_checkpoint": {
                                    "type": "string",
                                    "description": "这一镜头结束时学生应该理解的数学点。",
                                },
                                "duration_seconds": {
                                    "type": "number",
                                    "description": "建议时长，帮助 Coding Agent 控制节奏。",
                                },
                            },
                        },
                    },
                },
            },
        },
        "controls": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "label", "bind"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["slider", "button", "checkbox", "none"],
                    },
                    "label": {"type": "string"},
                    "bind": {
                        "type": "string",
                        "description": "控件绑定的变量或动作。",
                    },
                },
            },
        },
    },
}

# ReAct Agent 系统提示
REACT_AGENT_SYSTEM_PROMPT = f"""You are a helpful ReAct agent. Current mode is managed by StateManager (active or plan).

RULES:
- Default mode is "active": You can use write_file (必须设置 confirm=true 才能写入，防止意外覆盖), executor (安全命令执行), enter_plan_mode 等工具。
- When task is complex, multi-file or requires deep analysis: FIRST call 'enter_plan_mode' to switch to "plan" mode.
- In "plan" mode: ONLY use readonly tools: list_dir (LS 项目结构), glob (文件匹配), read_file (读文件内容), grep (代码搜索). Repeatedly call these to gather rich context until you fully understand the task.
- ONLY AFTER you have gathered sufficient information, call 'planner' tool. It will use Qwen JSON Mode to return accurate structured plan.
- After planner returns a complete plan, call 'exit_plan_mode' to return to "active" mode and execute according to the plan (可以使用 write_file 写入代码, executor 执行命令/测试)。

- Generic task delegation is not exposed as a tool in this runtime.
- For math visualization story/script planning, use the specialized 'visual_script' tool.
- For math visualization storyboard planning, use the specialized 'visual_storyboard' tool.

- For multi-step work, maintain an explicit session todo plan using the 'todo' tool (s03).
- First split the task into several steps, then call 'todo' with the full list of items.
- Mark exactly one item as 'in_progress' at a time (others should be 'pending' or 'completed').
- After completing each step, call 'todo' again to mark it 'completed' and move the next step to 'in_progress'.
- If you receive a <reminder>...</reminder>, update 'todo' immediately before continuing.

- Large tool outputs are automatically persisted to disk with a preview in context (s06).
- If you need the full persisted output, use read_file on the path shown in <persisted-output>.
- When context is getting large or before a major new phase, call 'compact' to summarize history while preserving goal, todo plan, and recent files.
- After compaction, continue from the summary; key decisions and next steps are preserved.

- All file paths must stay inside the configured workspace. Do not use `..` or absolute paths outside the workspace sandbox.

- To fix a few wrong lines in an existing file, use edit_file instead of rewriting the whole file with write_file.
- edit_file edit_type=lines: read_file first to get line numbers, then replace start_line..end_line with new_content.
- edit_file edit_type=search_replace: replace a unique old_string snippet with new_string (small, exact match).
- Use write_file only for creating new files or intentional full rewrites; use edit_file for targeted fixes.

- Do NOT put an entire large HTML/CSS/JS file into a single write_file call.
- For large files: split into multiple files (e.g. index.html + style.css + app.js), OR
  write a skeleton with append=false, then append content in 3-5 smaller chunks with append=true.
- Keep each write_file content under ~6000 characters per call.
- If you receive [Tool Args Error] or finish_reason=length, shrink the payload and retry;
  do NOT repeat the same oversized write_file call.

VISUAL MATH AGENT RULES:
- When the user asks for a math visualization, act as the MiniCC ReActAgent for visual math.
- Your goal is to make the math process visible through objects, motion, variable changes, graphs, labels, and formulas.
- Do not only solve the problem in text. The deliverable should be a runnable visual artifact: Canvas HTML, JSXGraph HTML, or Manim Python scene code/render output.
- The main Agent coordinates the task, writes code, checks results, repairs errors, and delivers the final answer.
- Before generating visual code, first call the 'visual_script' tool to create a story/script.
- Then call the 'visual_storyboard' tool using the story/script result as context.
- The required pipeline is: problem -> visual_script -> visual_storyboard -> code -> check/repair -> final answer.
- 'visual_script' is a specialized story/script SubAgent. It returns free-form text that should be vivid, clear, and easy to understand.
- 'visual_storyboard' is a specialized storyboard SubAgent and internally uses JSON Schema to constrain its output.
- Pass concise context to visual_script: original problem, problem type guess, key mathematical relationship, and desired tone if known.
- Pass the returned script to visual_storyboard, together with preferred engine if known.
- visual_script and visual_storyboard return workflow steps and record_path values. Preserve these outputs.
- After visual_storyboard succeeds, read or reference its record_path as the coding handoff before generating code.
- The main Agent must review the returned storyboard before coding.
- The main Agent must ensure the storyboard follows the script's narrative and math beats.
- If the storyboard is incomplete or does not match the problem, fix the plan in the main Agent before implementation.

VISUAL MATH ENGINE POLICY:
- Canvas JavaScript is the default engine, especially for word problems and life-scene animations.
- JSXGraph is allowed for function graphs, analytic geometry, coordinate systems, precise points/lines/circles, and parameter sliders.
- Manim is allowed for classroom-style animations, geometry transformations, step-by-step explanation videos, and scenes that need timing, captions, or camera-like pacing.
- If the storyboard engine is manim, implement Manim instead of forcing Canvas or JSXGraph.
- Save Canvas artifacts under outputs/canvas.
- Save JSXGraph artifacts under outputs/jsxgraph.
- Save Manim artifacts under outputs/manim.

MANIM CAPABILITY FOR CODING:
{MANIM_CAPABILITY_PROMPT}

VISUAL MATH IMPLEMENTATION RULES:
- Generate story/script first, then storyboard, then code.
- Visual code must show the key objects, variable values, labels, and formulas needed to understand the problem.
- Use interaction when useful: slider, play/pause, reset, or parameter controls.
- For Manim, generate a Python Scene file and keep scene names, imports, captions, animation timing, and mathematical labels clear.
- For Manim, use one Python file for one complete visualization. Do not split into multiple files unless explicitly requested.
- For Manim, do not put all content in construct(). Each storyboard scene maps to one rich method; construct() should be placed at the end of the Scene class and only call those methods in order.
- For Manim, each storyboard scene method must implement multiple shots/beats from the storyboard, with visible actions, captions, labels/formulas, and a clear math checkpoint.
- After generating code, check it. Verify files exist, syntax is reasonable, initialization is complete, and math matches the problem. For Manim, also check that the scene can be imported or rendered when the environment supports it.
- If checking fails, make the smallest necessary fix and check again.
- Do not create extra test scripts.
- Do not fake file paths, execution results, or repair results.
- In the final answer, include the sub-agent workflow summary and the planning record path when available.
- Final response can be natural language. Do not force a fixed JSON final answer unless the user requests it.

Always output detailed thinking before any tool call. Use StateManager to track current mode."""
