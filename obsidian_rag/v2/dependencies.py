from __future__ import annotations

from functools import lru_cache

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.v1.services.retrieval_service import RetrievalService


@lru_cache(maxsize=1)
def get_config() -> RagConfig:
    return load_config()


def get_retrieval_service() -> RetrievalService:
    return RetrievalService(get_config())
