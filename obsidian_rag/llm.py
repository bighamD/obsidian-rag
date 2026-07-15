from __future__ import annotations

import json
from collections.abc import Iterator

from openai import OpenAI
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict = Field(default_factory=dict)


class ToolCallingResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class OpenAIChatClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for ask")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def complete(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(model=self.model, messages=messages)
        return response.choices[0].message.content or ""

    def stream(self, messages: list[dict]) -> Iterator[str]:
        """只返回模型最终可见 content，不透传 reasoning_content。"""

        response = self.client.chat.completions.create(model=self.model, messages=messages, stream=True)
        for item in response:
            if not item.choices:
                continue
            content = item.choices[0].delta.content or ""
            if content:
                yield content

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
