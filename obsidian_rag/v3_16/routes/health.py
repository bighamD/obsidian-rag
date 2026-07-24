from fastapi import APIRouter, Depends

from obsidian_rag.v3_16.dependencies import get_learning_service
from obsidian_rag.v3_16.schemas import DeepAgentHealthResponse
from obsidian_rag.v3_16.service import DeepAgentLearningService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=DeepAgentHealthResponse)
def health(service: DeepAgentLearningService = Depends(get_learning_service)):
    checkpoint_ready = service.agent_factory().checkpoint_ready()
    runtime_store_ready = service.store.ready()
    sandbox_available = service.sandbox.runtime_status().available
    return DeepAgentHealthResponse(
        status="ok" if checkpoint_ready and runtime_store_ready else "degraded",
        version="v3.16",
        checkpoint_ready=checkpoint_ready,
        runtime_store_ready=runtime_store_ready,
        sandbox_available=sandbox_available,
    )

