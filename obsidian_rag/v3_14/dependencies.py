from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.core.sandbox import (
    ArtifactRegistry,
    DockerSandboxBackend,
    SandboxProfile,
    SandboxRuntime,
    SandboxWorkspaceManager,
)
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_10_2.runtime.lifecycle import StreamingAgentRuntimeService
from obsidian_rag.v3_12_3.dependencies import get_mcp_connection_manager
from obsidian_rag.v3_12_4.dependencies import get_collection_scope_resolver, get_config, get_knowledge_base_registry, get_retrieval_service
from obsidian_rag.v3_13.dependencies import get_permission_audit_store, get_permission_policy, get_skill_resolver
from obsidian_rag.v3_14.agent import SandboxAgentService
from obsidian_rag.v3_14.registry import build_sandbox_agent_tool_registry
from obsidian_rag.v3_14.service import SandboxLearningService


def get_sandbox_root() -> Path:
    return Path(os.getenv("RAG_SANDBOX_ROOT", ".rag-sandbox/runs")).expanduser()


@lru_cache(maxsize=1)
def get_sandbox_runtime() -> SandboxRuntime:
    root = get_sandbox_root()
    workspaces = SandboxWorkspaceManager(root)
    profile = SandboxProfile(
        image=os.getenv("RAG_SANDBOX_IMAGE", "python:3.12-slim"),
        timeout_seconds=int(os.getenv("RAG_SANDBOX_TIMEOUT_SECONDS", "15")),
    )
    backend = DockerSandboxBackend(profile, root.resolve())
    artifacts = ArtifactRegistry(workspaces)
    return SandboxRuntime(workspaces, backend, artifacts)


def build_agent() -> SandboxAgentService:
    config = get_config()
    retrieval = get_retrieval_service()
    sandbox = get_sandbox_runtime()
    registry, planner_tools, _ = build_sandbox_agent_tool_registry(
        retrieval,
        get_mcp_connection_manager(),
        sandbox,
    )
    return SandboxAgentService(
        retrieval_service=retrieval,
        retrieval_scope_resolver=get_collection_scope_resolver(),
        permission_policy=get_permission_policy(),
        skill_resolver=get_skill_resolver(),
        tool_registry=registry,
        planner_tools=planner_tools,
        sandbox_runtime=sandbox,
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
    return StreamingAgentRuntimeService(agent_factory=build_agent, run_store=get_run_store(), event_bus=get_event_bus())


@lru_cache(maxsize=1)
def get_learning_service() -> SandboxLearningService:
    return SandboxLearningService(
        runtime=get_runtime_service(),
        manager=get_mcp_connection_manager(),
        registry=get_knowledge_base_registry(),
        resolver=get_collection_scope_resolver(),
        policy=get_permission_policy(),
        audit_store=get_permission_audit_store(),
        skill_resolver=get_skill_resolver(),
        tool_registry_factory=lambda: build_sandbox_agent_tool_registry(
            get_retrieval_service(), get_mcp_connection_manager(), get_sandbox_runtime()
        )[0],
        sandbox=get_sandbox_runtime(),
    )
