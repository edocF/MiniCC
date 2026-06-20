"""LLM类，封装了LLM的调用逻辑。"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Generator, Optional

import openai
from dotenv import load_dotenv

from MiniCC.core.logger import get_logger

if TYPE_CHECKING:
    from MiniCC.messages.ai_message import AIMessage
    from MiniCC.messages.user_message import UserMessage

load_dotenv()

_log = get_logger("LLM")

_DEFAULT_MAX_TOKENS = int(os.getenv("MINICC_MAX_TOKENS", "16384"))


def _usage_to_dict(response: Any) -> dict[str, int]:
    """Extract OpenAI-compatible token usage from a completion response."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}

    def pick(*names: str) -> int:
        for name in names:
            value = getattr(usage, name, None)
            if value is not None:
                return int(value)
        if hasattr(usage, "model_dump"):
            data = usage.model_dump()
            for name in names:
                if data.get(name) is not None:
                    return int(data[name])
        return 0

    prompt_tokens = pick("prompt_tokens", "input_tokens")
    completion_tokens = pick("completion_tokens", "output_tokens")
    total_tokens = pick("total_tokens")
    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _check_truncation(response: Any) -> str | None:
    """Return finish_reason when the completion was truncated, else None."""
    if not response.choices:
        return None
    reason = getattr(response.choices[0], "finish_reason", None)
    if reason == "length":
        return reason
    return None


class LLM:
    def __init__(
        self,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        model_name: Optional[str] = None,
    ):
        """只支持Qwen系列模型，openai调用方式"""
        self.model_name = model_name or os.getenv("MODEL_NAME") or os.getenv("LLM_MODEL_ID")
        self.max_tokens = max_tokens if max_tokens is not None else _DEFAULT_MAX_TOKENS
        self.temperature = temperature
        self._client = openai.OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
        )
        self._token_usage_total = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        _log.info(f"LLM 初始化完成  model={self.model_name}")

    def reset_token_usage(self) -> None:
        """Reset token accounting for one Agent run."""
        self._token_usage_total = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def get_token_usage(self) -> dict[str, int]:
        """Return accumulated token usage since the last reset."""
        return dict(self._token_usage_total)

    def _record_token_usage(self, response: Any) -> dict[str, int]:
        usage = _usage_to_dict(response)
        if not usage:
            return {}
        for key in self._token_usage_total:
            self._token_usage_total[key] += usage.get(key, 0)
        _log.info(
            "LLM token usage  "
            f"prompt={usage.get('prompt_tokens', 0)}  "
            f"completion={usage.get('completion_tokens', 0)}  "
            f"total={usage.get('total_tokens', 0)}"
        )
        return usage

    def think(self, user_message: "UserMessage") -> "AIMessage":
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[user_message.to_openai_format()],
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        """TODO: 解析response为Message对象"""
        msg = response.choices[0].message
        usage = self._record_token_usage(response)
        metadata: dict[str, Any] = dict(getattr(msg, "metadata", None) or {})
        if usage:
            metadata["token_usage"] = usage
        from MiniCC.messages.ai_message import AIMessage

        return AIMessage(
            content=msg.content,
            metadata=metadata or None,
        )
    
    def stream_thinking(self, user_message: "UserMessage") -> Generator["AIMessage", None, None]:
        from MiniCC.messages.ai_message import AIMessage

        for chunk in self._client.chat.completions.create(
            model=self.model_name,
            messages=[user_message.to_openai_format()],
            stream=True,
        ):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = delta.content
            if not piece:
                continue
            yield AIMessage(
                content=piece,
                metadata=getattr(delta, "metadata", None),
            )

    def think_with_tools(self, messages: list, tools_or_registry=None) -> "AIMessage":
        """支持 Tool Calling 的思考方法。支持传入 Tool 列表或 ToolRegistry。
        已启用 Qwen 的 enable_thinking 参数以获取 reasoning_content。"""
        if hasattr(tools_or_registry, "to_openai_tools"):
            tool_schemas = tools_or_registry.to_openai_tools()
        else:
            tool_schemas = [t.to_openai_tool() for t in (tools_or_registry or [])]
        #print(f"Tool schemas: {tool_schemas}")

        request_kwargs = {
            "model": self.model_name,
            "messages": [m.to_openai_format() for m in messages],
            "max_tokens": self.max_tokens,
            "temperature": 0.3,  # 降低温度以提高 JSON 输出稳定性
            "tools": tool_schemas,
            "tool_choice": "auto",
            "extra_body": {"enable_thinking": True},
        }
        response = self._client.chat.completions.create(**request_kwargs)
        msg = response.choices[0].message
        usage = self._record_token_usage(response)
        finish_reason = _check_truncation(response)
        metadata: dict[str, Any] = dict(getattr(msg, "metadata", None) or {})
        if usage:
            metadata["token_usage"] = usage
        if finish_reason == "length":
            metadata["truncated"] = True
            metadata["finish_reason"] = finish_reason
            _log.warn(
                "LLM 输出被截断（finish_reason=length）。"
                "若含 tool_calls，请拆分 write_file 或减小单次 payload。"
            )

        # 提取 Qwen 的 reasoning_content（thinking 过程）
        reasoning_content = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)

        # 将 reasoning_content 直接封装到 content 中（按用户要求）
        final_content = msg.content or ""
        if reasoning_content:
            final_content = f"=== THINKING ===\n{reasoning_content}\n=== END THINKING ===\n\n{final_content}"

        if msg.tool_calls:
            from MiniCC.messages.tool_message import ToolCallMessage
            return ToolCallMessage(
                content=final_content,
                tool_calls=msg.tool_calls,
                metadata=metadata or None,
            )

        from MiniCC.messages.ai_message import AIMessage
        return AIMessage(
            content=final_content,
            metadata=metadata or None,
        )



"""测试"""
if __name__ == "__main__":
    from pydantic import BaseModel

    from MiniCC.messages.user_message import UserMessage
    from MiniCC.tools.base_tool import BaseTool
    from MiniCC.tools.tool_registry import ToolRegistry

    class WeatherArgs(BaseModel):
        city: str

    class MockWeatherTool(BaseTool):
        name = "get_weather"
        description = "Get current weather for a city."
        args_schema = WeatherArgs

        def execute(self, **kwargs: Any) -> Any:
            city = kwargs.get("city", "unknown")
            return f"{city} is sunny"

    _demo_log = get_logger("LLM.demo")
    llm = LLM()
    user_message = UserMessage("请使用工具查询北京天气")

    tool_registry = ToolRegistry()
    tool_registry.register(MockWeatherTool())
    response = llm.think_with_tools([user_message], tool_registry)
    for tool_call in response.tool_calls:
        tool = tool_registry.get_tool(tool_call.function.name)
        import json

        args = json.loads(tool_call.function.arguments)
        tool_result = tool.execute(**args)
        _demo_log.tool_result(tool_call.function.name, tool_result)