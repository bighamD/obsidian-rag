from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from obsidian_rag.v3_8_1.compaction import ConversationCompactor
from obsidian_rag.v3_8_1.dependencies import get_memory_compactor, get_memory_store
from obsidian_rag.v3_8_1.mysql_memory import MySQLConversationMemoryStore
from obsidian_rag.v3_8_1.schemas import MemoryCompactRequest, MemoryCompactResponse, MemorySnapshot

router = APIRouter()


@router.get("/memory/{conversation_id}", response_model=MemorySnapshot)
def get_conversation_memory(
    conversation_id: str,
    window: int = Query(default=20, ge=0, le=100),
    memory_store: MySQLConversationMemoryStore = Depends(get_memory_store),
) -> MemorySnapshot:
    return memory_store.load_snapshot(conversation_id, window=window)


@router.post("/memory/{conversation_id}/compact", response_model=MemoryCompactResponse)
def compact_conversation_memory(
    conversation_id: str,
    request: MemoryCompactRequest,
    compactor: ConversationCompactor = Depends(get_memory_compactor),
    memory_store: MySQLConversationMemoryStore = Depends(get_memory_store),
) -> MemoryCompactResponse:
    result = compactor.compact(
        conversation_id=conversation_id,
        keep_recent_turns=request.keep_recent_turns,
        trigger_turns=request.trigger_turns,
        trigger_tokens=request.trigger_tokens,
        force=request.force,
    )
    return MemoryCompactResponse(
        compaction=result,
        memory_snapshot=memory_store.load_snapshot(conversation_id, window=request.keep_recent_turns),
    )
