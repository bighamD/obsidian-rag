from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult


ToolSearchResult = SearchResult | RankedSearchResult


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    status: str
    results: list[ToolSearchResult] = field(default_factory=list)
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

    def search_notes(query: str, top_k: int, mode: str, filters=None, collection: str | None = None) -> ToolResult:
        search_kwargs = {"top_k": top_k, "mode": mode, "filters": filters}
        if collection is not None:
            search_kwargs["collection"] = collection
        results = retrieval_service.search(query, **search_kwargs)
        return ToolResult(
            tool_name="search_notes",
            status="success",
            results=list(results),
            metadata={"collection": _effective_collection_name(retrieval_service, collection)},
        )

    registry.register("search_notes", search_notes)
    return registry


def _effective_collection_name(retrieval_service, collection: str | None) -> str:
    resolver = getattr(retrieval_service, "collection_name", None)
    if callable(resolver):
        return str(resolver(collection))
    config = getattr(retrieval_service, "config", None)
    return collection or str(getattr(config, "collection_name", "obsidian_notes"))
