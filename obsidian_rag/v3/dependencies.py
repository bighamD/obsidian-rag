from __future__ import annotations

from functools import lru_cache

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3.agent.service import AgentService


@lru_cache(maxsize=1)
def get_config() -> RagConfig:
    return load_config()


def get_retrieval_service() -> RetrievalService:
    return RetrievalService(get_config())


def get_agent_service() -> AgentService:
    config = get_config()
    return AgentService(
        retrieval_service=get_retrieval_service(),
        chat_client_factory=lambda: OpenAIChatClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.chat_model,
        ),
    )
