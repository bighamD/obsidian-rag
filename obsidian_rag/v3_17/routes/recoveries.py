from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_17.dependencies import get_learning_service
from obsidian_rag.v3_17.schemas import DurableAgentAskResponse
from obsidian_rag.v3_17.service import DurableAgentLearningService


router = APIRouter(prefix="/recoveries", tags=["deepagents-checkpoint-recovery"])


@router.post("/{run_id}/retry", response_model=DurableAgentAskResponse)
def retry_failed_run(
    run_id: str,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    """从稳定 Thread 的最近 PostgreSQL Checkpoint 继续 failed Run。"""

    try:
        return service.recover(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/retry/stream", response_class=StreamingResponse)
def retry_failed_run_stream(
    run_id: str,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    """通过 SSE 观察 failed Run 的 Checkpoint 恢复过程。"""

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
