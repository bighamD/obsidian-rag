from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_10.dependencies import get_memory_store, get_run_store
from obsidian_rag.v3_10_2.runtime.event_bus import RunEventBus
from obsidian_rag.v3_11.agent.service import SkillAgentService
from obsidian_rag.v3_11.runtime.service import SkillRuntimeService
from obsidian_rag.v3_11.skills.registry import SkillRegistry


def get_config() -> RagConfig:
    return load_config()


def get_skill_root() -> Path:
    configured = os.getenv("RAG_SKILL_ROOT", "skills")
    return Path(configured).expanduser()


@lru_cache(maxsize=1)
def get_registry() -> SkillRegistry:
    registry = SkillRegistry(get_skill_root())
    registry.discover()
    return registry


@lru_cache(maxsize=1)
def get_event_bus() -> RunEventBus:
    return RunEventBus()


def build_agent() -> SkillAgentService:
    config = get_config()
    return SkillAgentService(
        retrieval_service=RetrievalService(config),
        registry=get_registry(),
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
def get_runtime_service() -> SkillRuntimeService:
    return SkillRuntimeService(
        agent_factory=build_agent,
        run_store=get_run_store(),
        event_bus=get_event_bus(),
    )
