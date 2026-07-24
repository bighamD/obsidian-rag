from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.v3_17.dependencies import get_learning_service
from obsidian_rag.v3_17.schemas import DurableConversationDeleteResponse, DurableConversationListResponse
from obsidian_rag.v3_17.service import DurableAgentLearningService


router = APIRouter(prefix="/conversations", tags=["durable-conversations"])


@router.get("", response_model=DurableConversationListResponse)
def list_conversations(
    tenant_id: str = Query(default="tenant_demo"),
    user_id: str = Query(default="user_demo"),
    assistant_id: str = Query(default="obsidian_rag"),
    limit: int = Query(default=50, ge=1, le=200),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    return service.conversations(tenant_id, user_id, assistant_id, limit)


@router.delete("/{conversation_id}", response_model=DurableConversationDeleteResponse)
def delete_conversation(
    conversation_id: str,
    tenant_id: str = Query(default="tenant_demo"),
    user_id: str = Query(default="user_demo"),
    assistant_id: str = Query(default="obsidian_rag"),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    try:
        result = service.delete_conversation(conversation_id, tenant_id, user_id, assistant_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not result.deleted:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
    return result

