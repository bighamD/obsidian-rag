from fastapi import APIRouter, Depends

from obsidian_rag.v3_11_1.dependencies import get_docling_service
from obsidian_rag.v3_11_1.schemas import DoclingRuntimeResponse
from obsidian_rag.v3_11_1.service import DoclingLearningService


router = APIRouter(tags=["runtime"])


@router.get("/runtime/config", response_model=DoclingRuntimeResponse)
def runtime_config(
    service: DoclingLearningService = Depends(get_docling_service),
) -> DoclingRuntimeResponse:
    return service.runtime()
