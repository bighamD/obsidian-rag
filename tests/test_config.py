from pathlib import Path

import pytest

from obsidian_rag.config import RagConfig, resolve_ingest_path


def _config(vault_path: Path | None = None) -> RagConfig:
    return RagConfig(
        api_key="test-key",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="gpt-5.4-mini",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
        embedding_provider="openai",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=Path(".rag/qdrant"),
        collection_name="obsidian_notes",
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.35,
        vault_path=vault_path,
    )


def test_resolve_ingest_path_prefers_cli_path():
    assert resolve_ingest_path(Path("/tmp/cli-vault"), _config(Path("/tmp/env-vault"))) == Path("/tmp/cli-vault")


def test_resolve_ingest_path_uses_configured_vault_path():
    assert resolve_ingest_path(None, _config(Path("/tmp/env-vault"))) == Path("/tmp/env-vault")


def test_resolve_ingest_path_requires_cli_or_configured_path():
    with pytest.raises(RuntimeError, match="RAG_VAULT_PATH"):
        resolve_ingest_path(None, _config())
