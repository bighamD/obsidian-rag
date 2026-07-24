from fastapi import APIRouter, Depends

from obsidian_rag.v3_12_3.dependencies import get_integration_service
from obsidian_rag.v3_12_3.schemas import McpAgentHealthResponse
from obsidian_rag.v3_12_3.service import McpAgentIntegrationService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=McpAgentHealthResponse)
def health(
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> McpAgentHealthResponse:
    runtime = service.mcp_runtime()
    connected = sum(server.status == "connected" for server in runtime.servers)
    return McpAgentHealthResponse(
        status="ok" if connected == len(runtime.servers) else "degraded",
        version="v3.12.3",
        mcp_started=runtime.started,
        connected_servers=connected,
        configured_servers=len(runtime.servers),
    )
