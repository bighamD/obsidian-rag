from fastapi import APIRouter, Depends

from obsidian_rag.v3_15.dependencies import get_learning_service
from obsidian_rag.v3_15.schemas import HitlHealthResponse
from obsidian_rag.v3_15.service import HitlLearningService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HitlHealthResponse)
def health(service: HitlLearningService = Depends(get_learning_service)):
    sandbox = service.sandbox.runtime_status()
    mcp = service.manager.runtime()
    checkpoint_ready = service.agent_factory().checkpoint_ready()
    runtime_store_ready = service.store.ready()
    return HitlHealthResponse(
        status="ok" if checkpoint_ready and runtime_store_ready and sandbox.available else "degraded",
        version="v3.15",
        checkpoint_ready=checkpoint_ready,
        runtime_store_ready=runtime_store_ready,
        sandbox_available=sandbox.available,
        connected_mcp_servers=sum(item.status == "connected" for item in mcp.servers),
    )
