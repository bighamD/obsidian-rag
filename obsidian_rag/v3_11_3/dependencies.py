from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from obsidian_rag.config import load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v1.services.retrieval_service import RetrievalService
from obsidian_rag.v3_11_3.registry import KnowledgeBaseRegistry
from obsidian_rag.v3_11_3.router import CollectionRouter
from obsidian_rag.v3_11_3.service import CollectionRouterService


def get_registry_path() -> Path:
    return Path(os.getenv("RAG_KNOWLEDGE_BASE_REGISTRY", "knowledge_bases.yaml")).expanduser()


@lru_cache(maxsize=1)
def get_registry() -> KnowledgeBaseRegistry:
    registry = KnowledgeBaseRegistry(get_registry_path())
    registry.load()
    return registry


@lru_cache(maxsize=1)
def get_collection_router_service() -> CollectionRouterService:
    config = load_config()
    return CollectionRouterService(
        config=config,
        registry=get_registry(),
        retrieval_service=RetrievalService(config),
        router=CollectionRouter(
            chat_client_factory=lambda: OpenAIChatClient(
                api_key=config.api_key,
                base_url=config.base_url,
                model=config.chat_model,
            )
        ),
    )
