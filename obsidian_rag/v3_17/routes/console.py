from fastapi import APIRouter, Depends, HTTPException, Query

from obsidian_rag.console_api.schemas import (
    ConsoleConfigResponse,
    ConsoleConversationDeleteResponse,
    ConsoleConversationListResponse,
    ConsoleConversationResponse,
    ConsoleEndpoints,
    ConsoleFeatures,
)
from obsidian_rag.v3_17.dependencies import get_learning_service
from obsidian_rag.v3_17.service import DurableAgentLearningService


router = APIRouter(prefix="/console", tags=["console-v1-durable"])


@router.get("/config", response_model=ConsoleConfigResponse)
def config() -> ConsoleConfigResponse:
    return ConsoleConfigResponse(
        contract_version="console.v1",
        backend_version="v3.17",
        features=ConsoleFeatures(
            json=True,
            sse=True,
            answer_delta=True,
            reasoning_delta=False,
            conversation_memory=True,
            conversation_management=True,
            collections=True,
            sandbox=True,
            hitl=True,
            deep_agents=True,
            durable_memory=True,
        ),
        endpoints=ConsoleEndpoints(
            ask="/agent/ask",
            stream="/agent/ask/stream",
            conversations="/console/conversations",
            conversation="/console/conversations/{conversation_id}",
            runs="/runs",
            sandbox_runtime="/runtime",
            sandbox_artifacts="/artifacts/runs/{run_id}",
            approvals="/approvals/{run_id}",
            approval_resume="/approvals/{run_id}/resume",
            approval_resume_stream="/approvals/{run_id}/resume/stream",
            memories="/memories",
            memory_audits="/memory-audits",
        ),
        default_memory_window=20,
    )


@router.get("/conversations", response_model=ConsoleConversationListResponse)
def conversations(
    limit: int = Query(default=50, ge=1, le=200),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    return service.console_conversations("tenant_demo", "user_demo", "obsidian_rag", limit)


@router.get("/conversations/{conversation_id}", response_model=ConsoleConversationResponse)
def conversation(
    conversation_id: str,
    window: int = Query(default=20, ge=0, le=100),
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    try:
        return service.console_conversation(conversation_id, window)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/conversations/{conversation_id}", response_model=ConsoleConversationDeleteResponse)
def delete_conversation(
    conversation_id: str,
    service: DurableAgentLearningService = Depends(get_learning_service),
):
    result = service.console_delete_conversation(conversation_id)
    if not result.deleted:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
    return result

