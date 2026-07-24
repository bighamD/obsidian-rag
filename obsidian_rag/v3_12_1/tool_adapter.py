from __future__ import annotations

from obsidian_rag.core.tools import ToolDefinition, ToolRegistry, ToolResult, build_search_tool_registry
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3_12.schemas import McpCallRequest
from obsidian_rag.v3_12.service import McpIntegrationService
from obsidian_rag.v3_12_1.schemas import (
    UnifiedToolCallRequest,
    UnifiedToolCallResponse,
    UnifiedToolDefinition,
    UnifiedToolListResponse,
)


class UnifiedToolService:
    """把本地检索 Tool 和 V3.12 MCP Adapter 注册到同一个公共 Registry。"""

    def __init__(self, retrieval_service, mcp_service: McpIntegrationService):
        self.retrieval_service = retrieval_service
        self.mcp_service = mcp_service

    async def list_tools(self) -> UnifiedToolListResponse:
        registry, errors = await self._registry()
        return UnifiedToolListResponse(
            tools=[UnifiedToolDefinition.from_core(item) for item in registry.list_tools()],
            errors=errors,
        )

    async def call(self, request: UnifiedToolCallRequest) -> UnifiedToolCallResponse:
        registry, _ = await self._registry()
        result = await registry.arun(request.name, **request.arguments)
        data = result.data
        if data is None and result.results:
            data = [to_search_hit(item).model_dump(mode="json") for item in result.results]
        return UnifiedToolCallResponse(
            name=request.name,
            status="success" if result.status == "success" else "failed",
            data=data,
            metadata=result.metadata,
            error=result.error,
        )

    async def _registry(self) -> tuple[ToolRegistry, dict[str, str]]:
        registry = build_search_tool_registry(self.retrieval_service)
        discovery = await self.mcp_service.list_tools()
        for tool in discovery.tools:
            async def call_mcp(_server=tool.server_name, _tool=tool.name, **arguments) -> ToolResult:
                response = await self.mcp_service.call_tool(
                    McpCallRequest(server_name=_server, tool_name=_tool, arguments=arguments)
                )
                return ToolResult(
                    tool_name=response.namespaced_name,
                    status=response.status,
                    error=response.error,
                    metadata={"source": "mcp", "duration_ms": response.duration_ms},
                    data=response.model_dump(mode="json"),
                )

            registry.register(
                tool.namespaced_name,
                call_mcp,
                ToolDefinition(
                    name=tool.namespaced_name,
                    description=tool.description or tool.title or tool.name,
                    input_schema=tool.input_schema,
                    read_only=tool.read_only,
                    source="mcp",
                ),
            )
        return registry, discovery.errors
