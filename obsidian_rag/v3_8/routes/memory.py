from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from obsidian_rag.v3_8.dependencies import get_memory_store
from obsidian_rag.v3_8.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_8.schemas import MemorySnapshot

router = APIRouter()


@router.get("/memory/{conversation_id}", response_model=MemorySnapshot)
def get_conversation_memory(
    conversation_id: str,
    window: int = Query(default=20, ge=0, le=100),
    memory_store: SQLiteConversationMemoryStore = Depends(get_memory_store),
) -> MemorySnapshot:
    return memory_store.load_snapshot(conversation_id, window=window)
