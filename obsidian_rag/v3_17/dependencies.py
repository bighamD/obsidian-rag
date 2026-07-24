from __future__ import annotations

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI
from langgraph.store.postgres import PostgresStore

from obsidian_rag.core.tools import build_search_tool_registry
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_12_4.dependencies import get_config, get_knowledge_base_registry, get_retrieval_service
from obsidian_rag.v3_14.dependencies import get_sandbox_runtime
from obsidian_rag.v3_15.dependencies import (
    close_postgres_pool as close_v315_postgres_pool,
    get_checkpoint_saver,
    get_postgres_pool,
    get_search_collection_policy,
)
from obsidian_rag.v3_16.dependencies import configure_harness_profile
from obsidian_rag.v3_17.agent import DurableDeepAgentService
from obsidian_rag.v3_17.memory import LongTermMemoryService
from obsidian_rag.v3_17.runtime import DurableAgentRuntimeService
from obsidian_rag.v3_17.service import DurableAgentLearningService
from obsidian_rag.v3_17.store import PostgresDurableAgentStore


@lru_cache(maxsize=1)
def get_model_context_tokens() -> int:
    return max(4000, int(os.getenv("RAG_V317_MODEL_CONTEXT_TOKENS", "128000")))


@lru_cache(maxsize=1)
def get_durable_store() -> PostgresDurableAgentStore:
    return PostgresDurableAgentStore(get_postgres_pool())


@lru_cache(maxsize=1)
def get_long_term_store() -> PostgresStore:
    store = PostgresStore(get_postgres_pool())
    store.setup()
    return store


@lru_cache(maxsize=1)
def get_memory_service() -> LongTermMemoryService:
    return LongTermMemoryService(get_long_term_store(), get_durable_store())


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    return RunEventBus()


def build_model():
    config = get_config()
    configure_harness_profile(config.chat_model)
    return ChatOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.chat_model,
        streaming=True,
        use_responses_api=False,
        max_retries=1,
        model_kwargs={"parallel_tool_calls": False},
        profile={
            "max_input_tokens": get_model_context_tokens(),
            "tool_calling": True,
            "tool_choice": True,
            "tool_call_streaming": True,
            "text_inputs": True,
            "text_outputs": True,
        },
    )


def build_agent() -> DurableDeepAgentService:
    config = get_config()
    registry = build_search_tool_registry(get_retrieval_service(), get_search_collection_policy())
    return DurableDeepAgentService(
        model_factory=build_model,
        search_registry=registry,
        knowledge_bases=get_knowledge_base_registry().list_manifests(enabled_only=True),
        sandbox_runtime=get_sandbox_runtime(),
        checkpointer=get_checkpoint_saver(),
        runtime_store=get_durable_store(),
        long_term_store=get_long_term_store(),
        memory_service=get_memory_service(),
        default_collection=config.collection_name,
        model_context_tokens=get_model_context_tokens(),
    )


@lru_cache(maxsize=1)
def get_runtime_service() -> DurableAgentRuntimeService:
    return DurableAgentRuntimeService(build_agent, get_durable_store(), get_event_bus())


@lru_cache(maxsize=1)
def get_learning_service() -> DurableAgentLearningService:
    return DurableAgentLearningService(
        runtime=get_runtime_service(),
        store=get_durable_store(),
        agent_factory=build_agent,
        sandbox=get_sandbox_runtime(),
        memory_service=get_memory_service(),
        long_term_store=get_long_term_store(),
        model_context_tokens=get_model_context_tokens(),
    )


def close_postgres_pool() -> None:
    get_learning_service.cache_clear()
    get_runtime_service.cache_clear()
    get_event_bus.cache_clear()
    get_memory_service.cache_clear()
    get_long_term_store.cache_clear()
    get_durable_store.cache_clear()
    get_model_context_tokens.cache_clear()
    close_v315_postgres_pool()

