from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_17.dependencies import get_learning_service
from obsidian_rag.v3_17.schemas import DurableAgentAskRequest, DurableAgentAskResponse
from obsidian_rag.v3_17.service import DurableAgentLearningService


router = APIRouter(prefix="/agent", tags=["deepagents-durable-memory"])


@router.post("/ask", response_model=DurableAgentAskResponse)
def ask(
    request: DurableAgentAskRequest,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    """使用稳定 conversation_id 恢复 Thread，并运行 DeepAgents Tool Loop。"""

    try:
        return service.ask(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(
    request: DurableAgentAskRequest,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    """通过 SSE 推送节点、工具、Summary 和终态响应。"""

    try:
        run_id = service.start_stream(request)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}", response_model=DurableAgentAskResponse)
def get_run(
    run_id: str,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    response = service.response(run_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Durable Agent Run not found: {run_id}")
    return response

