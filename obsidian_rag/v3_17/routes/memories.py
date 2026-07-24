from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.v3_17.dependencies import get_learning_service
from obsidian_rag.v3_17.schemas import (
    LongTermMemoryDeleteResponse,
    LongTermMemoryItem,
    LongTermMemoryListResponse,
    LongTermMemoryPutRequest,
    MemoryAuditListResponse,
)
from obsidian_rag.v3_17.service import DurableAgentLearningService


router = APIRouter(tags=["long-term-memory"])


@router.get("/memories", response_model=LongTermMemoryListResponse)
def list_memories(
    tenant_id: str = Query(default="tenant_demo"),
    user_id: str = Query(default="user_demo"),
    assistant_id: str = Query(default="obsidian_rag"),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    return service.memories(tenant_id, user_id, assistant_id)


@router.put("/memories", response_model=LongTermMemoryItem)
def put_memory(
    request: LongTermMemoryPutRequest,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    try:
        return service.put_memory(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/memories/{memory_id}", response_model=LongTermMemoryDeleteResponse)
def delete_memory(
    memory_id: str,
    tenant_id: str = Query(default="tenant_demo"),
    user_id: str = Query(default="user_demo"),
    assistant_id: str = Query(default="obsidian_rag"),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    return service.delete_memory(memory_id, tenant_id, user_id, assistant_id)


@router.get("/memory-audits", response_model=MemoryAuditListResponse)
def list_memory_audits(
    tenant_id: str = Query(default="tenant_demo"),
    user_id: str = Query(default="user_demo"),
    assistant_id: str = Query(default="obsidian_rag"),
    limit: int = Query(default=100, ge=1, le=500),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    return service.audits(tenant_id, user_id, assistant_id, limit)

