import sys
from pathlib import Path

import pytest

from obsidian_rag import cli
from obsidian_rag.config import RagConfig


def _config(tmp_path: Path) -> RagConfig:
    return RagConfig(
        api_key="test",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="test",
        embedding_model="test",
        embedding_dimensions=8,
        embedding_provider="hash",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=tmp_path / "qdrant",
        collection_name="obsidian_notes",
        min_score=0.0,
        vault_path=None,
    )


def test_ingest_cli_forwards_explicit_collection(monkeypatch, tmp_path: Path, capsys):
    captured = {}
    source = tmp_path / "recipes.md"
    config = _config(tmp_path)

    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "resolve_ingest_path", lambda path, request_config: path)

    def fake_ingest(path, config, recreate):
        captured.update(path=path, collection=config.collection_name, recreate=recreate)
        return 1, 2

    monkeypatch.setattr(cli, "ingest_path", fake_ingest)
    monkeypatch.setattr(sys, "argv", ["obsidian-rag", "ingest", str(source), "--collection", "recipes", "--recreate"])

    cli.main()

    assert captured == {"path": source, "collection": "recipes", "recreate": True}
    assert "in recipes" in capsys.readouterr().out


def test_search_cli_uses_default_collection(monkeypatch, tmp_path: Path, capsys):
    config = _config(tmp_path)
    captured = {}

    monkeypatch.setattr(cli, "load_config", lambda: config)

    def fake_search(query, config, top_k):
        captured.update(query=query, collection=config.collection_name, top_k=top_k)
        return []

    monkeypatch.setattr(cli, "search", fake_search)
    monkeypatch.setattr(sys, "argv", ["obsidian-rag", "search", "食品安全"])

    cli.main()

    assert captured == {"query": "食品安全", "collection": "obsidian_notes", "top_k": 5}
    assert "Collection: obsidian_notes" in capsys.readouterr().out


def test_cli_rejects_invalid_collection(monkeypatch, tmp_path: Path):
    config = _config(tmp_path)
    source = tmp_path / "food.md"

    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(sys, "argv", ["obsidian-rag", "ingest", str(source), "--collection", "Food Safety"])

    with pytest.raises(ValueError, match="collection"):
        cli.main()
