from __future__ import annotations

from openai import OpenAI


class OpenAIChatClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for ask")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat.completions.create(model=self.model, messages=messages)
        return response.choices[0].message.content or ""
