from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_8_1.agent.service import AgentService
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import RuntimeConfigResponse


def get_config() -> RagConfig:
    return load_config()


def default_memory_db_path() -> Path:
    """V3.10 使用独立 Memory DB，避免调试时混入 V3.8.1 会话。"""

    return Path(os.getenv("RAG_V3_10_MEMORY_DB_PATH", ".rag/v3_10_memory.sqlite3"))


def run_store_limit() -> int:
    return max(1, int(os.getenv("RAG_V3_10_RUN_STORE_LIMIT", "100")))


@lru_cache(maxsize=1)
def get_memory_store() -> SQLiteConversationMemoryStore:
    return SQLiteConversationMemoryStore(default_memory_db_path())


@lru_cache(maxsize=1)
def get_run_store() -> InMemoryRunStore:
    return InMemoryRunStore(limit=run_store_limit())


def get_agent_service() -> AgentService:
    config = get_config()
    return AgentService(
        retrieval_service=RetrievalService(config),
        chat_client_factory=lambda: OpenAIChatClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.chat_model,
        ),
        memory_store=get_memory_store(),
    )


def get_runtime_service() -> AgentRuntimeService:
    return AgentRuntimeService(agent_service=get_agent_service(), run_store=get_run_store())


def get_runtime_config() -> RuntimeConfigResponse:
    return RuntimeConfigResponse(
        run_store="InMemoryRunStore（进程重启后清空）",
        run_store_limit=run_store_limit(),
        token_estimation="中文字符约 2 字符/token、其他字符约 4 字符/token；仅覆盖 Answer prompt 与最终 answer。",
    )
