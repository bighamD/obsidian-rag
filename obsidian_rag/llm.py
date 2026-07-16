from __future__ import annotations

import json
from collections.abc import Iterator

from openai import OpenAI
from pydantic import BaseModel, Field

from obsidian_rag.core.llm import ChatStreamDelta


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class ToolCallingResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class OpenAIChatClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_stream_enabled: bool = False,
        reasoning_effort: str = "medium",
    ):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for ask")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.reasoning_stream_enabled = reasoning_stream_enabled
        self.reasoning_effort = reasoning_effort

    def complete(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(model=self.model, messages=messages)
        return response.choices[0].message.content or ""

    def stream(self, messages: list[dict]) -> Iterator[ChatStreamDelta]:
        """返回类型化 content；开关开启时额外适配 CPA reasoning_content。"""

        request = {"model": self.model, "messages": messages, "stream": True}
        if self.reasoning_stream_enabled:
            request["reasoning_effort"] = self.reasoning_effort
        response = self.client.chat.completions.create(**request)
        for item in response:
            if not item.choices:
                continue
            delta = item.choices[0].delta
            data = delta.model_dump(exclude_none=True)
            reasoning = data.get("reasoning_content") if self.reasoning_stream_enabled else None
            if reasoning:
                yield ChatStreamDelta(kind="reasoning", text=str(reasoning))
            content = data.get("content") or ""
            if content:
                yield ChatStreamDelta(kind="content", text=str(content))

    def complete_with_tools(self, messages: list[dict], tools: list[dict]) -> ToolCallingResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        tool_calls = []
        for call in message.tool_calls or []:
            arguments = call.function.arguments
            if isinstance(arguments, str):
                try:
                    parsed_arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    parsed_arguments = {}
            else:
                parsed_arguments = arguments or {}
            tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=parsed_arguments))
        return ToolCallingResponse(content=message.content, tool_calls=tool_calls)
