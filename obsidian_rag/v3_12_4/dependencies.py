from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.core.collections import (
    CollectionScopeResolver,
    KnowledgeBaseRegistry,
    LlmCollectionRouter,
)
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.reranking.retrieval import RerankingRetrievalService
from obsidian_rag.reranking.service import build_reranking_service
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_3.registry import build_agent_tool_registry
from obsidian_rag.v3_12_4.agent import RoutedMcpAgentService
from obsidian_rag.v3_12_4.service import UnifiedKnowledgeRoutingService


def get_config() -> RagConfig:
    return load_config()


def get_registry_path() -> Path:
    return Path(os.getenv("RAG_KNOWLEDGE_BASE_REGISTRY", "knowledge_bases.yaml")).expanduser()


@lru_cache(maxsize=1)
def get_knowledge_base_registry() -> KnowledgeBaseRegistry:
    registry = KnowledgeBaseRegistry(get_registry_path())
    registry.load()
    return registry


@lru_cache(maxsize=1)
def get_collection_scope_resolver() -> CollectionScopeResolver:
    config = get_config()
    return CollectionScopeResolver(
        registry=get_knowledge_base_registry(),
        default_collection=config.collection_name,
        router=LlmCollectionRouter(
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
                reasoning_stream_enabled=False,
            )
        ),
    )


def build_retrieval(config: RagConfig | None = None) -> RerankingRetrievalService:
    config = config or get_config()
    return RerankingRetrievalService(
        RetrievalService(config),
        build_reranking_service(config),
        config,
    )


def build_agent() -> RoutedMcpAgentService:
    config = get_config()
    retrieval = build_retrieval(config)
    registry, planner_tools, _ = build_agent_tool_registry(retrieval, get_mcp_connection_manager())
    return RoutedMcpAgentService(
        retrieval_service=retrieval,
        retrieval_scope_resolver=get_collection_scope_resolver(),
        tool_registry=registry,
        planner_tools=planner_tools,
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
        agent_factory=build_agent,
        run_store=get_run_store(),
        event_bus=get_event_bus(),
    )


@lru_cache(maxsize=1)
def get_integration_service() -> UnifiedKnowledgeRoutingService:
    return UnifiedKnowledgeRoutingService(
        runtime=get_runtime_service(),
        manager=get_mcp_connection_manager(),
        registry=get_knowledge_base_registry(),
        resolver=get_collection_scope_resolver(),
    )
