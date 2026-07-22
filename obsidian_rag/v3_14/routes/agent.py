from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskResponse
from obsidian_rag.v3_14.dependencies import get_learning_service
from obsidian_rag.v3_14.schemas import SandboxAskRequest, SandboxRuntimeConfigResponse
from obsidian_rag.v3_14.service import SandboxLearningService


router = APIRouter(prefix="/agent", tags=["agent-sandbox"])


@router.post("/ask", response_model=ProductionAskResponse)
def ask(request: SandboxAskRequest, service: SandboxLearningService = Depends(get_learning_service)):
    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(request: SandboxAskRequest, service: SandboxLearningService = Depends(get_learning_service)):
    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/runtime/config", response_model=SandboxRuntimeConfigResponse)
def runtime_config(service: SandboxLearningService = Depends(get_learning_service)):
    return service.runtime_config()
