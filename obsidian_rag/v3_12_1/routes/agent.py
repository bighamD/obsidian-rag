from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_12_1.dependencies import get_config, get_runtime_service
from obsidian_rag.v3_12_1.schemas import CoreAskRequest, CoreStreamConfigResponse
from obsidian_rag.v3_12_1.service import CoreRuntimeLearningService


router = APIRouter(prefix="/agent", tags=["agent-core"])


def get_learning_service() -> CoreRuntimeLearningService:
    config = get_config()
    return CoreRuntimeLearningService(
        get_runtime_service(),
        reasoning_stream_enabled=config.reasoning_stream_enabled,
        reasoning_effort=config.reasoning_effort,
    )


@router.post("/ask", response_model=ProductionAskResponse)
def ask(
    request: CoreAskRequest,
    service: CoreRuntimeLearningService = Depends(get_learning_service),
) -> ProductionAskResponse:
    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(
    request: CoreAskRequest,
    service: CoreRuntimeLearningService = Depends(get_learning_service),
) -> StreamingResponse:
    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/stream/config", response_model=CoreStreamConfigResponse)
def stream_config(
    service: CoreRuntimeLearningService = Depends(get_learning_service),
) -> CoreStreamConfigResponse:
    return service.config()
