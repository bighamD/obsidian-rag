from __future__ import annotations

from dataclasses import asdict, dataclass, field
from inspect import isawaitable
from typing import Any, Awaitable, Callable

from obsidian_rag.core.collections.policy import SearchCollectionPolicy
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
    risk_level: str | None = None
    required_permission: str | None = None
    scope: str | None = None


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


def build_search_tool_registry(
    retrieval_service,
    collection_policy: SearchCollectionPolicy | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()

    def search_notes(
        query: str,
        top_k: int,
        mode: str,
        filters=None,
        collection: str | None = None,
        collections: list[str] | None = None,
    ) -> ToolResult:
        requested_collections = (
            list(collections)
            if isinstance(collections, list)
            else [collection]
            if collection
            else []
        )
        retrieval_scope = None
        if collection_policy is not None:
            retrieval_scope = collection_policy.resolve(
                planner_collections=collections,
                explicit_collection=collection,
            )
            if not retrieval_scope.selected_collections:
                return ToolResult(
                    tool_name="search_notes",
                    status="failed" if retrieval_scope.status == "invalid_selection" else "success",
                    error=retrieval_scope.reason if retrieval_scope.status == "invalid_selection" else None,
                    metadata={
                        "retrieval_scope": retrieval_scope.model_dump(mode="json"),
                        "requested_collections": requested_collections,
                        "selected_collections": [],
                        "collection_errors": dict(retrieval_scope.errors),
                    },
                )
            collections = list(retrieval_scope.selected_collections)
            collection = None

        if collections is not None:
            if not collections:
                return ToolResult(
                    tool_name="search_notes",
                    status="success",
                    results=[],
                    metadata={"collections": [], "collection_errors": {}},
                )
            search_collections = getattr(retrieval_service, "search_collections", None)
            if not callable(search_collections):
                return ToolResult(
                    tool_name="search_notes",
                    status="failed",
                    error="当前 Retrieval Service 不支持多 Collection 检索。",
                    metadata={"collections": collections},
                )
            outcome, errors = search_collections(
                query,
                collections,
                top_k=top_k,
                mode=mode,
                filters=filters,
            )
            return ToolResult(
                tool_name="search_notes",
                status="success" if outcome.results else "failed" if errors else "success",
                results=list(outcome.results),
                error="; ".join(f"{key}: {value}" for key, value in errors.items()) if errors and not outcome.results else None,
                metadata={
                    "collections": list(collections),
                    "requested_collections": requested_collections,
                    "selected_collections": list(collections),
                    "collection_errors": errors,
                    "rerank": asdict(outcome.summary),
                    **(
                        {"retrieval_scope": retrieval_scope.model_dump(mode="json")}
                        if retrieval_scope is not None
                        else {}
                    ),
                },
            )
        search_kwargs = {"top_k": top_k, "mode": mode, "filters": filters}
        if collection is not None:
            search_kwargs["collection"] = collection
        results = retrieval_service.search(query, **search_kwargs)
        return ToolResult(
            tool_name="search_notes",
            status="success",
            results=list(results),
            metadata={
                "collection": _effective_collection_name(retrieval_service, collection),
                "selected_collections": [_effective_collection_name(retrieval_service, collection)],
                **(
                    {"retrieval_scope": retrieval_scope.model_dump(mode="json")}
                    if retrieval_scope is not None
                    else {}
                ),
            },
        )

    available_collections = (
        [item.collection for item in collection_policy.list_manifests()]
        if collection_policy is not None
        else []
    )
    collection_schema: dict[str, Any] = {"type": ["string", "null"]}
    collections_item_schema: dict[str, Any] = {"type": "string"}
    if available_collections:
        collection_schema["enum"] = [*available_collections, None]
        collections_item_schema["enum"] = available_collections
    registry.register(
        "search_notes",
        search_notes,
        ToolDefinition(
            name="search_notes",
            description=(
                "在 Planner 选择的知识库 collections 中执行 dense、keyword 或 hybrid 检索。"
                "Collection 会经过 Registry、数量上限和 Permission Policy 校验。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                    "mode": {"type": "string"},
                    "collection": collection_schema,
                    "collections": {
                        "type": "array",
                        "items": collections_item_schema,
                        "maxItems": collection_policy.max_collections if collection_policy is not None else 3,
                    },
                },
                "required": ["query", "top_k", "mode"],
            },
            read_only=True,
            risk_level="safe",
            required_permission="knowledge.read",
            scope="knowledge",
        ),
    )
    return registry


def _effective_collection_name(retrieval_service, collection: str | None) -> str:
    resolver = getattr(retrieval_service, "collection_name", None)
    if callable(resolver):
        return str(resolver(collection))
    config = getattr(retrieval_service, "config", None)
    return collection or str(getattr(config, "collection_name", "obsidian_notes"))
