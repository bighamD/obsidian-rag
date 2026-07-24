from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class ChatStreamDelta:
    """Chat 流中的类型化增量；reasoning 仅用于学习调试，不属于最终答案。"""

    kind: Literal["reasoning", "content"]
    text: str


class ChatClient(Protocol):
    """公共 Chat Client contract；Router 可只用 complete，Answer 可用 stream。"""

    def complete(self, messages: list[dict]) -> str: ...


class StreamingChatClient(ChatClient, Protocol):
    """支持 reasoning/content 类型化增量的 Chat Client contract。"""

    def stream(self, messages: list[dict]) -> Iterator[str | ChatStreamDelta]: ...
