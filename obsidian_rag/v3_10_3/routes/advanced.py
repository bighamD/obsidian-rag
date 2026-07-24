from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10_3.agent.service import AdvancedAgentService, STREAM_MODES
from obsidian_rag.v3_10_3.dependencies import get_advanced_agent_service, get_runtime_service
from obsidian_rag.v3_10_3.runtime.lifecycle import AdvancedStreamingRuntimeService
from obsidian_rag.v3_10_3.schemas import (
    AdvancedAskRequest,
    AdvancedAskResponse,
    AdvancedStreamConfigResponse,
    StateHistoryResponse,
)


router = APIRouter(prefix="/advanced", tags=["advanced-langgraph"])


@router.post("/ask", response_model=AdvancedAskResponse)
def ask_advanced(
    request: AdvancedAskRequest,
    runtime_service: AdvancedStreamingRuntimeService = Depends(get_runtime_service),
) -> AdvancedAskResponse:
    """同步执行 Advanced Graph，返回完整 JSON 和 State History 摘要计数。"""

    return runtime_service.ask(request)


@router.post("/ask/stream", response_class=StreamingResponse)
def stream_advanced(
    request: AdvancedAskRequest,
    runtime_service: AdvancedStreamingRuntimeService = Depends(get_runtime_service),
) -> StreamingResponse:
    """通过 SSE 返回 updates、messages 和 custom 三类 LangGraph 事件。"""

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


@router.get("/history/{thread_id}", response_model=StateHistoryResponse)
def get_state_history(
    thread_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="最多返回多少个 checkpoint 摘要。"),
    service: AdvancedAgentService = Depends(get_advanced_agent_service),
) -> StateHistoryResponse:
    """读取 InMemorySaver 中指定 thread_id 的 State History。"""

    return service.get_history(thread_id, limit=limit)


@router.get("/config", response_model=AdvancedStreamConfigResponse)
def advanced_config() -> AdvancedStreamConfigResponse:
    return AdvancedStreamConfigResponse(
        json_endpoint="/advanced/ask",
        stream_endpoint="/advanced/ask/stream",
        history_endpoint_template="/advanced/history/{thread_id}",
        stream_modes=list(STREAM_MODES),
        checkpointer="InMemorySaver（仅当前进程；重启后 State History 清空）",
    )

