from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from obsidian_rag.schema import SearchResult


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    status: str
    results: list[SearchResult] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[..., ToolResult]] = {}

    def register(self, name: str, handler: Callable[..., ToolResult]) -> None:
        self._tools[name] = handler

    def run(self, name: str, **kwargs) -> ToolResult:
        handler = self._tools.get(name)
        if handler is None:
            return ToolResult(tool_name=name, status="failed", error=f"Unknown tool: {name}")
        try:
            return handler(**kwargs)
        except Exception as exc:
            return ToolResult(tool_name=name, status="failed", error=str(exc), metadata={"error_type": type(exc).__name__})


def build_search_tool_registry(retrieval_service) -> ToolRegistry:
    registry = ToolRegistry()

    def search_notes(query: str, top_k: int, mode: str, filters=None) -> ToolResult:
        results = retrieval_service.search(query, top_k=top_k, mode=mode, filters=filters)
        return ToolResult(tool_name="search_notes", status="success", results=list(results))

    registry.register("search_notes", search_notes)
    return registry
