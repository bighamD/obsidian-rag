from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_15.dependencies import get_learning_service
from obsidian_rag.v3_15.schemas import HitlAskRequest, HitlAskResponse
from obsidian_rag.v3_15.service import HitlLearningService


router = APIRouter(prefix="/agent", tags=["agent-recovery-hitl"])


@router.post("/ask", response_model=HitlAskResponse)
def ask(request: HitlAskRequest, service: HitlLearningService = Depends(get_learning_service)):
    """执行 Agent；命中 confirm 时返回 waiting_for_approval，而不是执行 Tool。"""

    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(request: HitlAskRequest, service: HitlLearningService = Depends(get_learning_service)):
    """通过 SSE 执行 Agent；暂停事件同样携带完整 HitlAskResponse。"""

    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
