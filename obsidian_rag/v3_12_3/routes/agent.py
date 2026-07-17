from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_12_3.dependencies import get_integration_service
from obsidian_rag.v3_12_3.schemas import McpAgentAskRequest, McpAgentRuntimeConfigResponse
from obsidian_rag.v3_12_3.service import McpAgentIntegrationService


router = APIRouter(prefix="/agent", tags=["agent-mcp"])


@router.post("/ask", response_model=ProductionAskResponse)
def ask(
    request: McpAgentAskRequest,
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> ProductionAskResponse:
    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(
    request: McpAgentAskRequest,
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> StreamingResponse:
    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/runtime/config", response_model=McpAgentRuntimeConfigResponse)
def runtime_config(
    service: McpAgentIntegrationService = Depends(get_integration_service),
) -> McpAgentRuntimeConfigResponse:
    return service.runtime_config()
