from __future__ import annotations

from functools import lru_cache

from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
from langchain_openai import ChatOpenAI

from obsidian_rag.core.tools import build_search_tool_registry
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_12_4.dependencies import (
    get_config,
    get_knowledge_base_registry,
    get_retrieval_service,
)
from obsidian_rag.v3_14.dependencies import get_sandbox_runtime
from obsidian_rag.v3_15.dependencies import (
    close_postgres_pool as close_v315_postgres_pool,
    get_checkpoint_saver,
    get_postgres_pool,
    get_postgres_settings,
    get_search_collection_policy,
)
from obsidian_rag.v3_16.agent import DeepAgentService
from obsidian_rag.v3_16.runtime import DeepAgentRuntimeService
from obsidian_rag.v3_16.service import DeepAgentLearningService
from obsidian_rag.v3_16.store import PostgresDeepAgentStore


@lru_cache(maxsize=8)
def configure_harness_profile(model_name: str) -> None:
    """收紧 DeepAgents 默认工具集，保持 V3.16 的学习边界。"""

    profile_key = model_name if ":" in model_name else f"openai:{model_name}"
    register_harness_profile(
        profile_key,
        HarnessProfile(
            excluded_tools=frozenset({"execute", "write_todos"}),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )


@lru_cache(maxsize=1)
def get_deep_agent_store() -> PostgresDeepAgentStore:
    return PostgresDeepAgentStore(get_postgres_pool())


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
    )


def build_agent() -> DeepAgentService:
    config = get_config()
    registry = build_search_tool_registry(
        get_retrieval_service(),
        get_search_collection_policy(),
    )
    return DeepAgentService(
        model_factory=build_model,
        search_registry=registry,
        knowledge_bases=get_knowledge_base_registry().list_manifests(enabled_only=True),
        sandbox_runtime=get_sandbox_runtime(),
        checkpointer=get_checkpoint_saver(),
        store=get_deep_agent_store(),
        default_collection=config.collection_name,
    )


@lru_cache(maxsize=1)
def get_runtime_service() -> DeepAgentRuntimeService:
    return DeepAgentRuntimeService(build_agent, get_deep_agent_store(), get_event_bus())


@lru_cache(maxsize=1)
def get_learning_service() -> DeepAgentLearningService:
    return DeepAgentLearningService(
        runtime=get_runtime_service(),
        store=get_deep_agent_store(),
        agent_factory=build_agent,
        sandbox=get_sandbox_runtime(),
        postgres_settings=get_postgres_settings(),
    )


def close_postgres_pool() -> None:
    get_learning_service.cache_clear()
    get_runtime_service.cache_clear()
    get_deep_agent_store.cache_clear()
    configure_harness_profile.cache_clear()
    close_v315_postgres_pool()
