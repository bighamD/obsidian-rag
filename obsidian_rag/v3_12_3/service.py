from __future__ import annotations

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.connection import McpConnectionManager
from obsidian_rag.v3_12_3.schemas import (
    McpAgentAskRequest,
    McpAgentRuntimeConfigResponse,
    McpExplicitToolCallRequest,
    McpExplicitToolCallResponse,
    McpRefreshResponse,
    McpRuntimeResponse,
)


class McpAgentIntegrationService:
    """V3.12.3 JSON/SSE Agent 与持久 MCP Runtime 的应用服务。"""

    def __init__(self, runtime: StreamingAgentRuntimeService, manager: McpConnectionManager):
        self.runtime = runtime
        self.manager = manager

    def ask(self, request: McpAgentAskRequest) -> ProductionAskResponse:
        return self.runtime.ask(request)

    def start_stream(self, request: McpAgentAskRequest) -> str:
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        return self.runtime.stream(run_id)

    def mcp_runtime(self) -> McpRuntimeResponse:
        return self.manager.runtime()

    def refresh_mcp(self, server_name: str | None = None, *, reconnect: bool = False) -> McpRefreshResponse:
        runtime = self.manager.refresh(server_name, reconnect=reconnect)
        return McpRefreshResponse(
            refreshed_servers=[server_name] if server_name else [server.name for server in runtime.servers],
            runtime=runtime,
        )

    def call_tool(self, request: McpExplicitToolCallRequest) -> McpExplicitToolCallResponse:
        return McpExplicitToolCallResponse(
            name=request.name,
            result=self.manager.call_tool(request.name, request.arguments),
        )

    def runtime_config(self) -> McpAgentRuntimeConfigResponse:
        return McpAgentRuntimeConfigResponse(
            version="v3.12.3",
            json_endpoint="/agent/ask",
            stream_endpoint="/agent/ask/stream",
            mcp_runtime_endpoint="/mcp/runtime",
            transports=["stdio", "streamable_http"],
            persistent_sessions=True,
            planner_tool_selection=True,
            permission_policy_enabled=False,
            sandbox_enabled=False,
        )
