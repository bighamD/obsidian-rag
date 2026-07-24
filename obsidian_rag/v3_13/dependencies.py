from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.dependencies import (
    get_collection_scope_resolver,
    get_config,
    get_knowledge_base_registry,
    get_retrieval_service,
)
from obsidian_rag.core.permissions import InMemoryPermissionAuditStore, StaticPermissionPolicy
from obsidian_rag.core.skills import CoreSkillResolver, LlmSkillRouter, SkillRegistry
from obsidian_rag.v3_13.agent import PermissionAwareAgentService
from obsidian_rag.v3_13.registry import build_permission_agent_tool_registry
from obsidian_rag.v3_13.service import PermissionLearningService


@lru_cache(maxsize=1)
def get_permission_audit_store() -> InMemoryPermissionAuditStore:
    return InMemoryPermissionAuditStore()


@lru_cache(maxsize=1)
def get_permission_policy() -> StaticPermissionPolicy:
    return StaticPermissionPolicy(get_permission_audit_store())


def get_skill_root() -> Path:
    return Path(os.getenv("RAG_SKILL_ROOT", "skills")).expanduser()


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    registry = SkillRegistry(get_skill_root())
    registry.discover()
    return registry


@lru_cache(maxsize=1)
def get_skill_resolver() -> CoreSkillResolver:
    config = get_config()
    return CoreSkillResolver(
        registry=get_skill_registry(),
        router=LlmSkillRouter(
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
                reasoning_stream_enabled=False,
            )
        ),
    )


def build_agent() -> PermissionAwareAgentService:
    config = get_config()
    retrieval = get_retrieval_service()
    registry, planner_tools, _ = build_permission_agent_tool_registry(
        retrieval,
        get_mcp_connection_manager(),
    )
    return PermissionAwareAgentService(
        retrieval_service=retrieval,
        retrieval_scope_resolver=get_collection_scope_resolver(),
        permission_policy=get_permission_policy(),
        skill_resolver=get_skill_resolver(),
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
def get_learning_service() -> PermissionLearningService:
    return PermissionLearningService(
        runtime=get_runtime_service(),
        manager=get_mcp_connection_manager(),
        registry=get_knowledge_base_registry(),
        resolver=get_collection_scope_resolver(),
        policy=get_permission_policy(),
        audit_store=get_permission_audit_store(),
        skill_resolver=get_skill_resolver(),
        tool_registry_factory=lambda: build_permission_agent_tool_registry(
            get_retrieval_service(),
            get_mcp_connection_manager(),
        )[0],
    )
