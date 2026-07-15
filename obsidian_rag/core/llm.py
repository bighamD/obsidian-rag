from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class ChatClient(Protocol):
    """公共 Chat Client contract；Router 可只用 complete，Answer 可用 stream。"""

    def complete(self, messages: list[dict]) -> str: ...


class StreamingChatClient(ChatClient, Protocol):
    """支持最终可见答案增量的 Chat Client contract。"""

    def stream(self, messages: list[dict]) -> Iterator[str]: ...
