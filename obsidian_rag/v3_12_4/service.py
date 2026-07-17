from __future__ import annotations

from obsidian_rag.core.collections import KnowledgeBaseRegistry, RetrievalScopeRequest, RetrievalScopeResolver
from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.connection import McpConnectionManager
from obsidian_rag.v3_12_3.schemas import (
    McpExplicitToolCallRequest,
    McpExplicitToolCallResponse,
    McpRefreshResponse,
    McpRuntimeResponse,
)
from obsidian_rag.v3_12_4.schemas import (
    CollectionRouteDebugRequest,
    CollectionRouteDebugResponse,
    CollectionRuntimeResponse,
    RoutedMcpAskRequest,
    RoutedMcpRuntimeConfigResponse,
)


class UnifiedKnowledgeRoutingService:
    """统一 Agent、Collection Routing 与持久 MCP Runtime 的应用服务。"""

    def __init__(
        self,
        runtime: StreamingAgentRuntimeService,
        manager: McpConnectionManager,
        registry: KnowledgeBaseRegistry,
        resolver: RetrievalScopeResolver,
    ):
        self.runtime = runtime
        self.manager = manager
        self.registry = registry
        self.resolver = resolver

    def ask(self, request: RoutedMcpAskRequest) -> ProductionAskResponse:
        return self.runtime.ask(request)

    def start_stream(self, request: RoutedMcpAskRequest) -> str:
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        return self.runtime.stream(run_id)

    def route_collection(self, request: CollectionRouteDebugRequest) -> CollectionRouteDebugResponse:
        scope = self.resolver.resolve(
            RetrievalScopeRequest(
                question=request.question,
                explicit_collection=request.collection,
                router_enabled=request.collection_router_enabled,
                max_collections=request.max_collections,
            )
        )
        return CollectionRouteDebugResponse(question=request.question, scope=scope)

    def collection_runtime(self) -> CollectionRuntimeResponse:
        manifests = self.registry.list_manifests()
        return CollectionRuntimeResponse(
            registry_path=str(self.registry.path),
            knowledge_bases=manifests,
            enabled_ids=[item.id for item in manifests if item.enabled],
            errors=list(self.registry.errors),
        )

    def mcp_runtime(self) -> McpRuntimeResponse:
        return self.manager.runtime()

    def refresh_mcp(self, server_name: str | None = None, *, reconnect: bool = False) -> McpRefreshResponse:
        runtime = self.manager.refresh(server_name, reconnect=reconnect)
        return McpRefreshResponse(
            refreshed_servers=[server_name] if server_name else [item.name for item in runtime.servers],
            runtime=runtime,
        )

    def call_tool(self, request: McpExplicitToolCallRequest) -> McpExplicitToolCallResponse:
        return McpExplicitToolCallResponse(
            name=request.name,
            result=self.manager.call_tool(request.name, request.arguments),
        )

    def runtime_config(self) -> RoutedMcpRuntimeConfigResponse:
        return RoutedMcpRuntimeConfigResponse(
            version="v3.12.4",
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            collection_runtime_endpoint="/collections/runtime",
            collection_route_endpoint="/collections/route",
            mcp_runtime_endpoint="/mcp/runtime",
            transports=["stdio", "streamable_http"],
            persistent_mcp_sessions=True,
            collection_routing=True,
            multi_collection_reranking=True,
            permission_policy_enabled=False,
        )
