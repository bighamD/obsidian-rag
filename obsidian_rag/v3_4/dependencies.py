from __future__ import annotations

from obsidian_rag.config import RagConfig, load_config
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_4.planner.service import PlannerService


def get_config() -> RagConfig:
    return load_config()


def build_chat_client(config: RagConfig) -> OpenAIChatClient:
    return OpenAIChatClient(api_key=config.api_key, base_url=config.base_url, model=config.chat_model)


def get_planner_service() -> PlannerService:
    config = get_config()
    return PlannerService(chat_client_factory=lambda: build_chat_client(config))
