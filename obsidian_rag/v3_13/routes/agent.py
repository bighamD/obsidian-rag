from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_13.dependencies import get_learning_service
from obsidian_rag.v3_13.schemas import PermissionAskRequest, PermissionRuntimeConfigResponse
from obsidian_rag.v3_13.service import PermissionLearningService


router = APIRouter(prefix="/agent", tags=["agent-permission-policy"])


@router.post("/ask", response_model=ProductionAskResponse)
def ask(
    request: PermissionAskRequest,
    service: PermissionLearningService = Depends(get_learning_service),
) -> ProductionAskResponse:
    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(
    request: PermissionAskRequest,
    service: PermissionLearningService = Depends(get_learning_service),
) -> StreamingResponse:
    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/runtime/config", response_model=PermissionRuntimeConfigResponse)
def runtime_config(
    service: PermissionLearningService = Depends(get_learning_service),
) -> PermissionRuntimeConfigResponse:
    return service.runtime_config()
