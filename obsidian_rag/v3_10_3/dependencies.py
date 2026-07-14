from __future__ import annotations

from functools import lru_cache

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_4.planner.service import PlannerService
from obsidian_rag.v3_8_1.compaction import ConversationCompactor
from obsidian_rag.v3_10.dependencies import get_memory_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_3.agent.service import AdvancedAgentService
from obsidian_rag.v3_10_3.llm import OpenAICompatibleChatModel
from obsidian_rag.v3_10_3.runtime.lifecycle import AdvancedStreamingRuntimeService


def get_config() -> RagConfig:
    return load_config()


@lru_cache(maxsize=1)
def get_advanced_agent_service() -> AdvancedAgentService:
    config = get_config()
    memory_store = get_memory_store()

    def build_chat_client() -> OpenAIChatClient:
        return OpenAIChatClient(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.chat_model,
        )

    return AdvancedAgentService(
        retrieval_service=RetrievalService(config),
        planner_service=PlannerService(chat_client_factory=build_chat_client),
        chat_model=OpenAICompatibleChatModel(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.chat_model,
        ),
        memory_store=memory_store,
        memory_compactor=ConversationCompactor(
            memory_store=memory_store,
            chat_client_factory=build_chat_client,
        ),
    )


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    return RunEventBus()


def get_runtime_service() -> AdvancedStreamingRuntimeService:
    return AdvancedStreamingRuntimeService(
        agent_service=get_advanced_agent_service(),
        event_bus=get_event_bus(),
    )

