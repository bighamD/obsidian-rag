from fastapi import APIRouter, Depends, Query

from obsidian_rag.config import RagConfig
from obsidian_rag.console_api.dependencies import get_console_config, get_console_memory_store
from obsidian_rag.console_api.schemas import (
    ConsoleConfigResponse,
    ConsoleConversationResponse,
    ConsoleEndpoints,
    ConsoleFeatures,
)


router = APIRouter(prefix="/console", tags=["console-v1"])


@router.get("/config", response_model=ConsoleConfigResponse)
def console_config(config: RagConfig = Depends(get_console_config)) -> ConsoleConfigResponse:
    return ConsoleConfigResponse(
        contract_version="console.v1",
        backend_version="v3.12.1",
        features=ConsoleFeatures(
            json_api=True,
            sse=True,
            answer_delta=True,
            reasoning_delta=config.reasoning_stream_enabled,
            conversation_memory=True,
            collections=True,
        ),
        endpoints=ConsoleEndpoints(
            ask="/agent/ask",
            stream="/agent/ask/stream",
            conversation="/console/conversations/{conversation_id}",
            runs="/runs",
        ),
        default_memory_window=3,
    )


@router.get("/conversations/{conversation_id}", response_model=ConsoleConversationResponse)
def get_conversation(
    conversation_id: str,
    window: int = Query(default=3, ge=0, le=20, description="读取最近多少条原始 Turn。"),
    memory_store=Depends(get_console_memory_store),
) -> ConsoleConversationResponse:
    return ConsoleConversationResponse(
        conversation_id=conversation_id,
        memory_snapshot=memory_store.load_snapshot(conversation_id, window=window),
    )
