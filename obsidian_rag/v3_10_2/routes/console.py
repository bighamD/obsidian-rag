from fastapi import APIRouter, Depends, Query

from obsidian_rag.v3_10.dependencies import get_memory_store
from obsidian_rag.v3_10_1.schemas import ConsoleConversationResponse
from obsidian_rag.v3_10_2.schemas import StreamConfigResponse


router = APIRouter(prefix="/console", tags=["console"])


@router.get("/config", response_model=StreamConfigResponse)
def console_config() -> StreamConfigResponse:
    return StreamConfigResponse(
        api_mode="json+sse",
        streaming_available=True,
        stream_endpoint="/agent/ask/stream",
        default_memory_window=3,
    )


@router.get("/conversations/{conversation_id}", response_model=ConsoleConversationResponse)
def get_conversation(
    conversation_id: str,
    window: int = Query(default=3, ge=0, le=20, description="读取最近多少条原始 Turn。"),
    memory_store=Depends(get_memory_store),
) -> ConsoleConversationResponse:
    return ConsoleConversationResponse(
        conversation_id=conversation_id,
        memory_snapshot=memory_store.load_snapshot(conversation_id, window=window),
    )

