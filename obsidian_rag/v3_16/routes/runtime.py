from fastapi import APIRouter, Depends

from obsidian_rag.v3_16.dependencies import get_learning_service
from obsidian_rag.v3_16.schemas import DeepAgentRuntimeConfigResponse
from obsidian_rag.v3_16.service import DeepAgentLearningService


router = APIRouter(tags=["deepagents-runtime"])


@router.get("/runtime", response_model=DeepAgentRuntimeConfigResponse)
def runtime(service: DeepAgentLearningService = Depends(get_learning_service)):
    return service.runtime_config()

