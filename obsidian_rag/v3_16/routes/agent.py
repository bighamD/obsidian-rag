from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_16.dependencies import get_learning_service
from obsidian_rag.v3_16.schemas import DeepAgentAskRequest, DeepAgentAskResponse
from obsidian_rag.v3_16.service import DeepAgentLearningService


router = APIRouter(prefix="/agent", tags=["deepagents-tool-loop"])


@router.post("/ask", response_model=DeepAgentAskResponse)
def ask(
    request: DeepAgentAskRequest,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    """执行 Deep Agent；write_file 前返回 waiting_for_approval。"""

    return service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def ask_stream(
    request: DeepAgentAskRequest,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    """通过 SSE 推送 model/tool/approval/terminal 公开事件。"""

    run_id = service.start_stream(request)
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}", response_model=DeepAgentAskResponse)
def get_run(
    run_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    """读取一个已产生终态或待审批快照的 Deep Agent Run。"""

    response = service.response(run_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"Deep Agent Run not found: {run_id}")
    return response


@router.get("/runs/{run_id}/approval")
def get_run_approval(
    run_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    """按 roadmap 路径读取当前 Run 的审批记录。"""

    approval = service.approval(run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval not found: {run_id}")
    return approval

