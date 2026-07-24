from fastapi import APIRouter, Depends, Query

from obsidian_rag.v3_12_3.schemas import McpRefreshResponse, McpRuntimeResponse
from obsidian_rag.v3_13.dependencies import get_learning_service
from obsidian_rag.v3_13.schemas import PermissionMcpCallRequest, PermissionMcpCallResponse
from obsidian_rag.v3_13.service import PermissionLearningService


router = APIRouter(prefix="/mcp", tags=["mcp-permission-policy"])


@router.get("/runtime", response_model=McpRuntimeResponse)
def runtime(
    service: PermissionLearningService = Depends(get_learning_service),
) -> McpRuntimeResponse:
    return service.mcp_runtime()


@router.post("/refresh", response_model=McpRefreshResponse)
def refresh(
    server_name: str | None = Query(default=None, description="为空时刷新全部 Server。"),
    reconnect: bool = Query(default=False, description="是否先断开并重新连接。"),
    service: PermissionLearningService = Depends(get_learning_service),
) -> McpRefreshResponse:
    return service.refresh_mcp(server_name, reconnect=reconnect)


@router.post("/call", response_model=PermissionMcpCallResponse)
def call(
    request: PermissionMcpCallRequest,
    service: PermissionLearningService = Depends(get_learning_service),
) -> PermissionMcpCallResponse:
    return service.call_mcp(request)
