from fastapi import APIRouter, Depends

from obsidian_rag.v3_12.dependencies import get_mcp_service
from obsidian_rag.v3_12.schemas import McpHealthResponse
from obsidian_rag.v3_12.service import McpIntegrationService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=McpHealthResponse)
def health(service: McpIntegrationService = Depends(get_mcp_service)) -> McpHealthResponse:
    return McpHealthResponse(
        status="ok",
        version="v3.12",
        configured_servers=len(service.list_servers()),
    )
