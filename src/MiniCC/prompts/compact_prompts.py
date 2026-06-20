"""Compact / context compression prompts (s06)."""

COMPACT_SYSTEM_PROMPT = """You summarize a ReAct agent conversation for continuity after context compression.
Preserve: current goal, completed actions, files read/modified, key decisions/constraints, next steps.
Be concise but complete enough for the agent to continue working without re-reading everything."""


def get_compact_user_prompt(
    conversation_text: str,
    todo_render: str,
    recent_files: list[str],
) -> str:
    files_block = "\n".join(f"- {p}" for p in recent_files) if recent_files else "(none tracked)"
    return f"""Summarize this conversation for continuity. The agent will continue from your summary.

Current todo plan:
{todo_render}

Recent files touched:
{files_block}

Conversation to summarize:
{conversation_text}

Output a structured summary covering: goal, completed work, files, decisions, next step."""
