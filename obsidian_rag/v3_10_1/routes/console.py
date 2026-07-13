from fastapi import APIRouter, Depends, Query

from obsidian_rag.v3_10.dependencies import get_memory_store
from obsidian_rag.v3_10_1.schemas import ConsoleConfigResponse, ConsoleConversationResponse


router = APIRouter(prefix="/console", tags=["console"])


@router.get("/config", response_model=ConsoleConfigResponse)
def console_config() -> ConsoleConfigResponse:
    """返回 UI 可安全读取的前端模式与默认值。"""

    return ConsoleConfigResponse(
        api_mode="json",
        streaming_available=False,
        default_memory_window=3,
    )


@router.get("/conversations/{conversation_id}", response_model=ConsoleConversationResponse)
def get_conversation(
    conversation_id: str,
    window: int = Query(default=3, ge=0, le=20, description="读取最近多少条原始 Turn。"),
    memory_store=Depends(get_memory_store),
) -> ConsoleConversationResponse:
    """读取供 Console 恢复显示的 V3.10 Conversation Memory 快照。"""

    return ConsoleConversationResponse(
        conversation_id=conversation_id,
        memory_snapshot=memory_store.load_snapshot(conversation_id, window=window),
    )
