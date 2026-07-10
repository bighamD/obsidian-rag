from __future__ import annotations

from functools import lru_cache

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_8.agent.service import AgentService
from obsidian_rag.v3_8.memory import SQLiteConversationMemoryStore, default_memory_db_path


def get_config() -> RagConfig:
    return load_config()


def build_chat_client(config: RagConfig) -> OpenAIChatClient:
    return OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model)


@lru_cache(maxsize=1)
def get_memory_store() -> SQLiteConversationMemoryStore:
    return SQLiteConversationMemoryStore(default_memory_db_path())


def get_agent_service() -> AgentService:
    config = get_config()
    retrieval_service = RetrievalService(config)
    return AgentService(
        retrieval_service=retrieval_service,
        chat_client_factory=lambda: build_chat_client(config),
        memory_store=get_memory_store(),
    )
