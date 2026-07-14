from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store
from obsidian_rag.v3_8_1.agent.service import AgentService
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService


def get_config() -> RagConfig:
    return load_config()


def default_memory_db_path() -> Path:
    return Path(os.getenv("RAG_V3_10_MEMORY_DB_PATH", ".rag/v3_10_memory.sqlite3"))


def build_agent() -> AgentService:
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


def get_runtime_service() -> StreamingAgentRuntimeService:
    return StreamingAgentRuntimeService(agent_factory=build_agent, run_store=get_run_store(), event_bus=get_event_bus())


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    return RunEventBus()

