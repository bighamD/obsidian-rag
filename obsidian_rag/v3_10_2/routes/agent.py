from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_10.schemas import ProductionAskRequest, ProductionAskResponse
from obsidian_rag.v3_10_2.dependencies import get_runtime_service
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService


router = APIRouter(tags=["agent"])


@router.post("/agent/ask", response_model=ProductionAskResponse)
def ask_agent(
    request: ProductionAskRequest,
    runtime_service: StreamingAgentRuntimeService = Depends(get_runtime_service),
) -> ProductionAskResponse:
    """V3.10.2 兼容 JSON 接口；不使用 SSE。"""

    return runtime_service.ask(request)


@router.post("/agent/ask/stream", response_class=StreamingResponse)
def stream_agent(
    request: ProductionAskRequest,
    runtime_service: StreamingAgentRuntimeService = Depends(get_runtime_service),
) -> StreamingResponse:
    """以 SSE 返回节点、工具、trace 和最终响应事件。"""

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

