from fastapi import APIRouter, Depends

from obsidian_rag.v3_10.dependencies import get_runtime_service
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.schemas import ProductionAskRequest, ProductionAskResponse


router = APIRouter(tags=["agent"])


@router.post("/agent/ask", response_model=ProductionAskResponse)
def ask_agent(
    request: ProductionAskRequest,
    runtime_service: AgentRuntimeService = Depends(get_runtime_service),
) -> ProductionAskResponse:
    """运行 V3.8.1 Agent，并返回统一的 Run 生命周期记录和原始 Agent 响应。"""

    return runtime_service.ask(request)
