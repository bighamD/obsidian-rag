from fastapi import APIRouter, Depends

from obsidian_rag.v3_11_2.dependencies import get_framework_comparison_service
from obsidian_rag.v3_11_2.schemas import FrameworkRuntimeResponse
from obsidian_rag.v3_11_2.service import FrameworkComparisonService


router = APIRouter(tags=["runtime"])


@router.get("/runtime/config", response_model=FrameworkRuntimeResponse)
def runtime_config(
    service: FrameworkComparisonService = Depends(get_framework_comparison_service),
) -> FrameworkRuntimeResponse:
    return service.runtime()
