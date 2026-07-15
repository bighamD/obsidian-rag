from __future__ import annotations

from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, Awaitable, Callable

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
    data: Any = None


@dataclass(frozen=True)
class ToolDefinition:
    """本地和 MCP Tool 共用的稳定发现契约。"""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    read_only: bool | None = None
    source: str = "local"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[..., ToolResult | Awaitable[ToolResult]]] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., ToolResult | Awaitable[ToolResult]],
        definition: ToolDefinition | None = None,
    ) -> None:
        self._tools[name] = handler
        self._definitions[name] = definition or ToolDefinition(name=name)

    def list_tools(self) -> list[ToolDefinition]:
        return [self._definitions[name] for name in sorted(self._definitions)]

    def run(self, name: str, **kwargs) -> ToolResult:
        handler = self._tools.get(name)
        if handler is None:
            return ToolResult(tool_name=name, status="failed", error=f"Unknown tool: {name}")
        try:
            result = handler(**kwargs)
            if isawaitable(result):
                return ToolResult(
                    tool_name=name,
                    status="failed",
                    error="Async tool requires ToolRegistry.arun()",
                )
            return result
        except Exception as exc:
            return ToolResult(tool_name=name, status="failed", error=str(exc), metadata={"error_type": type(exc).__name__})

    async def arun(self, name: str, **kwargs) -> ToolResult:
        handler = self._tools.get(name)
        if handler is None:
            return ToolResult(tool_name=name, status="failed", error=f"Unknown tool: {name}")
        try:
            result = handler(**kwargs)
            return await result if isawaitable(result) else result
        except Exception as exc:
            return ToolResult(
                tool_name=name,
                status="failed",
                error=str(exc),
                metadata={"error_type": type(exc).__name__},
            )


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

    registry.register(
        "search_notes",
        search_notes,
        ToolDefinition(
            name="search_notes",
            description="在指定知识库 collection 中执行 dense、keyword 或 hybrid 检索。",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                    "mode": {"type": "string"},
                    "collection": {"type": ["string", "null"]},
                },
                "required": ["query", "top_k", "mode"],
            },
            read_only=True,
        ),
    )
    return registry


def _effective_collection_name(retrieval_service, collection: str | None) -> str:
    resolver = getattr(retrieval_service, "collection_name", None)
    if callable(resolver):
        return str(resolver(collection))
    config = getattr(retrieval_service, "config", None)
    return collection or str(getattr(config, "collection_name", "obsidian_notes"))
