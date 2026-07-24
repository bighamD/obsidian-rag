from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from obsidian_rag.v3_15.schemas import (
    ApprovalListResponse,
    ApprovalRecord,
    ApprovalResumeRequest,
)
from obsidian_rag.v3_16.dependencies import get_learning_service
from obsidian_rag.v3_16.schemas import DeepAgentAskResponse
from obsidian_rag.v3_16.service import DeepAgentLearningService


router = APIRouter(prefix="/approvals", tags=["deepagents-hitl"])


@router.get("", response_model=ApprovalListResponse)
def list_approvals(
    status: Literal["pending", "resolved"] | None = Query(default=None, description="按审批状态过滤。"),
    limit: int = Query(default=50, ge=1, le=200, description="最多返回多少条审批记录。"),
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    return service.approvals(status, limit)


@router.get("/{run_id}", response_model=ApprovalRecord)
def get_approval(
    run_id: str,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    approval = service.approval(run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"Approval not found: {run_id}")
    return approval


@router.post("/{run_id}/resume", response_model=DeepAgentAskResponse)
def resume(
    run_id: str,
    request: ApprovalResumeRequest,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    try:
        return service.resume(run_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/resume/stream", response_class=StreamingResponse)
def resume_stream(
    run_id: str,
    request: ApprovalResumeRequest,
    service: DeepAgentLearningService = Depends(get_learning_service),
):
    try:
        service.start_resume_stream(run_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return StreamingResponse(
        service.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

