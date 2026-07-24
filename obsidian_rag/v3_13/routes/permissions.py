from fastapi import APIRouter, Depends, Query

from obsidian_rag.v3_13.dependencies import get_learning_service
from obsidian_rag.v3_13.schemas import (
    PermissionAuditListResponse,
    PermissionEvaluateRequest,
    PermissionEvaluateResponse,
)
from obsidian_rag.v3_13.service import PermissionLearningService


router = APIRouter(prefix="/permissions", tags=["permission-policy"])


@router.post("/evaluate", response_model=PermissionEvaluateResponse)
def evaluate(
    request: PermissionEvaluateRequest,
    service: PermissionLearningService = Depends(get_learning_service),
) -> PermissionEvaluateResponse:
    return service.evaluate(request)


@router.get("/audit", response_model=PermissionAuditListResponse)
def audit(
    limit: int = Query(default=50, ge=1, le=200, description="最多返回多少条最近权限审计记录。"),
    service: PermissionLearningService = Depends(get_learning_service),
) -> PermissionAuditListResponse:
    return service.audit(limit)
