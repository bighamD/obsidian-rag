from __future__ import annotations

from typing import Protocol

from obsidian_rag.core.collections.schemas import RetrievalScope, RetrievalScopeRequest


class RetrievalScopeResolver(Protocol):
    """Agent Core 使用的知识库范围解析扩展点。"""

    def resolve(self, request: RetrievalScopeRequest) -> RetrievalScope: ...
