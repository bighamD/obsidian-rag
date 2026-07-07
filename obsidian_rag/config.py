from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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
    chunk_size: int
    chunk_overlap: int
    min_score: float
    vault_path: Path | None


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
        collection_name=os.getenv("RAG_COLLECTION", "obsidian_notes"),
        chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1200")),
        chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "150")),
        min_score=float(os.getenv("RAG_MIN_SCORE", "0.35")),
        vault_path=_optional_path(os.getenv("RAG_VAULT_PATH")),
    )


def require_api_key(config: RagConfig) -> None:
    if config.embedding_provider == "openai" and not config.api_key:
        raise RuntimeError("OPENAI_API_KEY is required when RAG_EMBED_PROVIDER=openai")


def resolve_ingest_path(cli_path: Path | None, config: RagConfig) -> Path:
    if cli_path is not None:
        return cli_path
    if config.vault_path is not None:
        return config.vault_path
    raise RuntimeError("Provide an ingest path or set RAG_VAULT_PATH in .env")


def _optional_path(value: str | None) -> Path | None:
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()


def _optional_str(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()
