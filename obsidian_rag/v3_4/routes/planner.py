from __future__ import annotations

from fastapi import APIRouter, Depends

from obsidian_rag.v3_4.dependencies import get_planner_service
from obsidian_rag.v3_4.planner.service import PlannerService
from obsidian_rag.v3_4.schemas import PlanRequest, PlanResponse

router = APIRouter()


@router.post("/planner/plan", response_model=PlanResponse)
def planner_plan(
    request: PlanRequest,
    planner_service: PlannerService = Depends(get_planner_service),
) -> PlanResponse:
    return planner_service.plan(request)
