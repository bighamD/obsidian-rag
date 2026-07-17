from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.v3_12_3.dependencies import get_integration_service
from obsidian_rag.v3_12_3.schemas import (
    McpExplicitToolCallRequest,
    McpExplicitToolCallResponse,
    McpRefreshResponse,
    McpRuntimeResponse,
)
from obsidian_rag.v3_12_3.service import McpAgentIntegrationService


router = APIRouter(prefix="/mcp", tags=["mcp-runtime"])


@router.get("/runtime", response_model=McpRuntimeResponse)
def runtime(
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> McpRuntimeResponse:
    return service.mcp_runtime()


@router.post("/refresh", response_model=McpRefreshResponse)
def refresh(
    server_name: str | None = Query(default=None, description="只刷新指定 Server；为空刷新全部。"),
    reconnect: bool = Query(default=False, description="是否先断开并重新建立 Session。"),
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> McpRefreshResponse:
    try:
        return service.refresh_mcp(server_name, reconnect=reconnect)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/call", response_model=McpExplicitToolCallResponse)
def call_tool(
    request: McpExplicitToolCallRequest,
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> McpExplicitToolCallResponse:
    try:
        return service.call_tool(request)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
