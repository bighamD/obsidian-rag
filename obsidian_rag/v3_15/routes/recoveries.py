from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_15.dependencies import get_learning_service
from obsidian_rag.v3_15.schemas import HitlAskResponse
from obsidian_rag.v3_15.service import HitlLearningService


router = APIRouter(prefix="/recoveries", tags=["checkpoint-recovery"])


@router.post("/{run_id}/retry", response_model=HitlAskResponse)
def retry_failed_run(run_id: str, service: HitlLearningService = Depends(get_learning_service)):
    """从失败节点前的最近 Checkpoint 继续执行。"""

    try:
        return service.recover(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/retry/stream", response_class=StreamingResponse)
def retry_failed_run_stream(run_id: str, service: HitlLearningService = Depends(get_learning_service)):
    """通过 SSE 观察失败节点恢复执行。"""

    try:
        service.start_recovery_stream(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
