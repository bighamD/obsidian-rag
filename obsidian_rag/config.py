from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv


COLLECTION_NAME_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,62}$"
COLLECTION_NAME_RE = re.compile(COLLECTION_NAME_PATTERN)


@dataclass(frozen=True)
class RagConfig:
    api_key: str
    base_url: str
    chat_model: str
    embedding_model: str
    embedding_dimensions: int
    embedding_provider: str
    ollama_base_url: str
    qdrant_url: str | None
    db_path: Path
    collection_name: str
    min_score: float
    vault_path: Path | None
    docling_tokenizer_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_token_size: int = 512
    chunk_strategy: str = "adaptive_parent_child"
    parent_chunk_tokens: int = 1000
    child_chunk_tokens: int = 400
    child_chunk_overlap: int = 40
    reasoning_stream_enabled: bool = False
    reasoning_effort: str = "medium"


def load_config() -> RagConfig:
    load_dotenv()
    return RagConfig(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", "http://127.0.0.1:8317/v1"),
        chat_model=os.getenv("RAG_CHAT_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("RAG_EMBED_MODEL", "text-embedding-3-small"),
        embedding_dimensions=int(os.getenv("RAG_EMBED_DIMENSIONS", "1536")),
        embedding_provider=os.getenv("RAG_EMBED_PROVIDER", "openai"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        qdrant_url=_optional_str(os.getenv("QDRANT_URL")),
        db_path=Path(os.getenv("RAG_DB_PATH", ".rag/qdrant")),
        collection_name=validate_collection_name(os.getenv("RAG_COLLECTION", "obsidian_notes")),
        min_score=float(os.getenv("RAG_MIN_SCORE", "0.35")),
        vault_path=_optional_path(os.getenv("RAG_VAULT_PATH")),
        docling_tokenizer_model=os.getenv(
            "RAG_DOCLING_TOKENIZER_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        chunk_token_size=int(os.getenv("RAG_CHUNK_TOKENS", "512")),
        chunk_strategy=os.getenv("RAG_CHUNK_STRATEGY", "adaptive_parent_child").strip().lower(),
        parent_chunk_tokens=int(os.getenv("RAG_PARENT_CHUNK_TOKENS", "1000")),
        child_chunk_tokens=int(os.getenv("RAG_CHILD_CHUNK_TOKENS", "400")),
        child_chunk_overlap=int(os.getenv("RAG_CHILD_CHUNK_OVERLAP", "40")),
        reasoning_stream_enabled=_env_bool("RAG_REASONING_STREAM_ENABLED", False),
        reasoning_effort=os.getenv("RAG_REASONING_EFFORT", "medium").strip() or "medium",
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def require_api_key(config: RagConfig) -> None:
    if config.embedding_provider == "openai" and not config.api_key:
        raise RuntimeError("OPENAI_API_KEY is required when RAG_EMBED_PROVIDER=openai")


def resolve_ingest_path(cli_path: Path | None, config: RagConfig) -> Path:
    if cli_path is not None:
        return cli_path
    if config.vault_path is not None:
        return config.vault_path
    raise RuntimeError("Provide an ingest path or set RAG_VAULT_PATH in .env")


def with_collection(config: RagConfig, collection: str | None = None) -> RagConfig:
    """返回本次请求的 collection 配置副本，不修改共享全局 config。"""

    selected = config.collection_name if collection is None else collection
    return replace(config, collection_name=validate_collection_name(selected))


def validate_collection_name(value: str) -> str:
    """校验用户可读且可安全映射到 Qdrant / 本地索引文件的 collection 名称。"""

    if not isinstance(value, str) or not COLLECTION_NAME_RE.fullmatch(value):
        raise ValueError(
            "collection 必须匹配 "
            f"{COLLECTION_NAME_PATTERN}，例如 food_safety 或 recipes。"
        )
    return value


def _optional_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()


def _optional_str(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()
