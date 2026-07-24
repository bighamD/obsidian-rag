from fastapi import APIRouter, Depends

from obsidian_rag.v3_13.dependencies import get_learning_service
from obsidian_rag.v3_13.schemas import SkillRouteDebugRequest, SkillRouteDebugResponse, SkillRuntimeResponse
from obsidian_rag.v3_13.service import PermissionLearningService


router = APIRouter(prefix="/skills", tags=["core-skill-router"])


@router.get("/runtime", response_model=SkillRuntimeResponse)
def runtime(service: PermissionLearningService = Depends(get_learning_service)) -> SkillRuntimeResponse:
    return service.skill_runtime()


@router.post("/route", response_model=SkillRouteDebugResponse)
def route(
    request: SkillRouteDebugRequest,
    service: PermissionLearningService = Depends(get_learning_service),
) -> SkillRouteDebugResponse:
    return service.route_skill(request)
