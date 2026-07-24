from fastapi import APIRouter, Depends

from obsidian_rag.v3_12_4.dependencies import get_integration_service
from obsidian_rag.v3_12_4.schemas import RoutedMcpHealthResponse
from obsidian_rag.v3_12_4.service import UnifiedKnowledgeRoutingService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=RoutedMcpHealthResponse)
def health(
    service: UnifiedKnowledgeRoutingService = Depends(get_integration_service),
) -> RoutedMcpHealthResponse:
    mcp = service.mcp_runtime()
    collections = service.collection_runtime()
    connected = sum(1 for item in mcp.servers if item.status == "connected")
    degraded = bool(mcp.errors or collections.errors)
    return RoutedMcpHealthResponse(
        status="degraded" if degraded else "ok",
        version="v3.12.4",
        mcp_started=mcp.started,
        connected_mcp_servers=connected,
        enabled_knowledge_bases=len(collections.enabled_ids),
        registry_error_count=len(collections.errors),
    )
