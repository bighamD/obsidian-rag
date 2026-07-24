from fastapi import APIRouter, Depends

from obsidian_rag.v3_17.dependencies import get_learning_service
from obsidian_rag.v3_17.schemas import DurableHealthResponse, DurableRuntimeConfigResponse
from obsidian_rag.v3_17.service import DurableAgentLearningService


router = APIRouter(tags=["durable-runtime"])


@router.get("/runtime", response_model=DurableRuntimeConfigResponse)
def runtime(service: DurableAgentLearningService = Depends(get_learning_service)):
    return service.runtime_config()


@router.get("/health", response_model=DurableHealthResponse)
def health(service: DurableAgentLearningService = Depends(get_learning_service)):
    return service.health()

