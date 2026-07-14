from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    convert_to_openai_messages,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from openai import OpenAI
from pydantic import Field, PrivateAttr, SecretStr


class OpenAICompatibleChatModel(BaseChatModel):
    """把现有 OpenAI-compatible endpoint 适配为 LangChain ChatModel。

    `_stream()` 产生 `AIMessageChunk`，LangGraph 才能通过
    `stream_mode="messages"` 捕获最终答案增量。模型隐藏推理不会进入 content。
    """

    model_name: str = Field(alias="model")
    api_key: SecretStr
    base_url: str
    _client: OpenAI = PrivateAttr()

    def model_post_init(self, context: Any) -> None:
        self._client = OpenAI(api_key=self.api_key.get_secret_value(), base_url=self.base_url)

    @property
    def _llm_type(self) -> str:
        return "openai-compatible-v3-10-3"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_name": self.model_name, "base_url": self.base_url}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=convert_to_openai_messages(messages),
            stop=stop,
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=convert_to_openai_messages(messages),
            stop=stop,
            stream=True,
            **kwargs,
        )
        for item in response:
            if not item.choices:
                continue
            content = item.choices[0].delta.content or ""
            if content:
                yield ChatGenerationChunk(message=AIMessageChunk(content=content))

