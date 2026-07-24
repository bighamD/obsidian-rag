from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_12_2.dependencies import get_learning_service
from obsidian_rag.v3_12_2.schemas import RerankAskRequest, RerankRuntimeConfigResponse
from obsidian_rag.v3_12_2.service import RerankerLearningService


router = APIRouter(prefix="/agent", tags=["agent-reranking"])


@router.post("/ask", response_model=ProductionAskResponse)
def ask(request: RerankAskRequest, service: RerankerLearningService = Depends(get_learning_service)):
    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(request: RerankAskRequest, service: RerankerLearningService = Depends(get_learning_service)):
    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/stream/config", response_model=RerankRuntimeConfigResponse)
def stream_config(service: RerankerLearningService = Depends(get_learning_service)):
    return service.runtime_config()
