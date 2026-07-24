from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.v3_12.dependencies import get_mcp_service
from obsidian_rag.v3_12.schemas import (
    McpCallRequest,
    McpServerInfo,
    McpToolCallResponse,
    McpToolListResponse,
)
from obsidian_rag.v3_12.service import McpIntegrationService


router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers", response_model=list[McpServerInfo])
def list_servers(service: McpIntegrationService = Depends(get_mcp_service)) -> list[McpServerInfo]:
    return service.list_servers()


@router.get("/tools", response_model=McpToolListResponse)
async def list_tools(
    server_name: str | None = Query(default=None, description="只发现指定 Server；为空时发现全部 Server。"),
    service: McpIntegrationService = Depends(get_mcp_service),
) -> McpToolListResponse:
    try:
        return await service.list_tools(server_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/call", response_model=McpToolCallResponse)
async def call_tool(
    request: McpCallRequest,
    service: McpIntegrationService = Depends(get_mcp_service),
) -> McpToolCallResponse:
    return await service.call_tool(request)
