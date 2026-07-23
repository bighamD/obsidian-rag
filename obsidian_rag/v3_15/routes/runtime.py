from fastapi import APIRouter, Depends

from obsidian_rag.v3_15.dependencies import get_learning_service
from obsidian_rag.v3_15.schemas import HitlRuntimeConfigResponse
from obsidian_rag.v3_15.service import HitlLearningService


router = APIRouter(prefix="/hitl", tags=["recovery-runtime"])


@router.get("/runtime", response_model=HitlRuntimeConfigResponse)
def runtime(service: HitlLearningService = Depends(get_learning_service)):
    return service.runtime_config()
