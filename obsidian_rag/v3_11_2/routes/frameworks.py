from fastapi import APIRouter, Depends, HTTPException

from obsidian_rag.v3_11_2.dependencies import get_framework_comparison_service
from obsidian_rag.v3_11_2.schemas import FrameworkCompareRequest, FrameworkCompareResponse
from obsidian_rag.v3_11_2.service import FrameworkComparisonService


router = APIRouter(prefix="/frameworks", tags=["framework-comparison"])


@router.post("/compare", response_model=FrameworkCompareResponse)
def compare_frameworks(
    request: FrameworkCompareRequest,
    service: FrameworkComparisonService = Depends(get_framework_comparison_service),
) -> FrameworkCompareResponse:
    try:
        return service.compare(request)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
