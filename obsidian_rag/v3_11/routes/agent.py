from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_11.dependencies import get_runtime_service
from obsidian_rag.v3_11.runtime.service import SkillRuntimeService
from obsidian_rag.v3_11.schemas import SkillAskRequest, SkillProductionAskResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/ask", response_model=SkillProductionAskResponse)
def ask_agent(
    request: SkillAskRequest,
    runtime_service: SkillRuntimeService = Depends(get_runtime_service),
) -> SkillProductionAskResponse:
    """同步执行 Skill Router + V3.8.1 Agent，并返回 JSON。"""

    return runtime_service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def stream_agent(
    request: SkillAskRequest,
    runtime_service: SkillRuntimeService = Depends(get_runtime_service),
) -> StreamingResponse:
    """以 SSE 推送 Skill 选择、Agent 节点和最终响应事实事件。"""

    run_id = runtime_service.start_stream(request)
    return StreamingResponse(
        runtime_service.stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
