from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_8_1.agent.service import AgentService
from obsidian_rag.v3_8_1.memory import SQLiteConversationMemoryStore
from obsidian_rag.v3_9.evaluation.evaluator import AgentEvaluator


def get_config() -> RagConfig:
    return load_config()


def default_agent_eval_memory_db_path() -> Path:
    """使用独立数据库保存评测运行产生的 V3.8.1 原始 Turns。"""

    return Path(os.getenv("RAG_V3_9_EVAL_MEMORY_DB_PATH", ".rag/v3_9_eval_memory.sqlite3"))


@lru_cache(maxsize=1)
def get_memory_store() -> SQLiteConversationMemoryStore:
    return SQLiteConversationMemoryStore(default_agent_eval_memory_db_path())


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


def get_agent_evaluator() -> AgentEvaluator:
    return AgentEvaluator(get_agent_service())
