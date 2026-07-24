from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_12_4.dependencies import get_integration_service
from obsidian_rag.v3_12_4.schemas import RoutedMcpAskRequest, RoutedMcpRuntimeConfigResponse
from obsidian_rag.v3_12_4.service import UnifiedKnowledgeRoutingService


router = APIRouter(prefix="/agent", tags=["agent-knowledge-routing"])


@router.post("/ask", response_model=ProductionAskResponse)
def ask(
    request: RoutedMcpAskRequest,
    service: UnifiedKnowledgeRoutingService = Depends(get_integration_service),
) -> ProductionAskResponse:
    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(
    request: RoutedMcpAskRequest,
    service: UnifiedKnowledgeRoutingService = Depends(get_integration_service),
) -> StreamingResponse:
    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/runtime/config", response_model=RoutedMcpRuntimeConfigResponse)
def runtime_config(
    service: UnifiedKnowledgeRoutingService = Depends(get_integration_service),
) -> RoutedMcpRuntimeConfigResponse:
    return service.runtime_config()
