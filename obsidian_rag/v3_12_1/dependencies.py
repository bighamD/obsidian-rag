from __future__ import annotations

from functools import lru_cache

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.core.agent.service import AgentService
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12.dependencies import get_mcp_service
from obsidian_rag.v3_12_1.tool_adapter import UnifiedToolService


def get_config() -> RagConfig:
    return load_config()


def build_core_agent() -> AgentService:
    config = get_config()
    return AgentService(
        retrieval_service=RetrievalService(config),
        chat_client_factory=lambda: OpenAIChatClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.chat_model,
            reasoning_stream_enabled=config.reasoning_stream_enabled,
            reasoning_effort=config.reasoning_effort,
        ),
        memory_store=get_memory_store(),
    )


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    return RunEventBus()


@lru_cache(maxsize=1)
def get_runtime_service() -> StreamingAgentRuntimeService:
    return StreamingAgentRuntimeService(
        agent_factory=build_core_agent,
        run_store=get_run_store(),
        event_bus=get_event_bus(),
    )


@lru_cache(maxsize=1)
def get_tool_service() -> UnifiedToolService:
    config = get_config()
    return UnifiedToolService(RetrievalService(config), get_mcp_service())
