from fastapi import APIRouter, Depends

from obsidian_rag.v3_12_1.dependencies import get_tool_service
from obsidian_rag.v3_12_1.schemas import (
    UnifiedToolCallRequest,
    UnifiedToolCallResponse,
    UnifiedToolListResponse,
)
from obsidian_rag.v3_12_1.tool_adapter import UnifiedToolService


router = APIRouter(prefix="/tools", tags=["unified-tool-registry"])


@router.get("", response_model=UnifiedToolListResponse)
async def list_tools(service: UnifiedToolService = Depends(get_tool_service)) -> UnifiedToolListResponse:
    return await service.list_tools()


@router.post("/call", response_model=UnifiedToolCallResponse)
async def call_tool(
    request: UnifiedToolCallRequest,
    service: UnifiedToolService = Depends(get_tool_service),
) -> UnifiedToolCallResponse:
    return await service.call(request)
