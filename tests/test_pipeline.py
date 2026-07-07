from pathlib import Path

from obsidian_rag.config import RagConfig
from obsidian_rag.pipeline import answer, make_store
from obsidian_rag.schema import SearchResult, TextChunk


def _config(db_path: Path, qdrant_url: str | None = None) -> RagConfig:
    return RagConfig(
        api_key="test-key",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="gpt-5.4-mini",
        embedding_model="qwen3-embedding:0.6b",
        embedding_dimensions=1024,
        embedding_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=qdrant_url,
        db_path=db_path,
        collection_name="obsidian_notes",
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.35,
        vault_path=Path("/tmp/vault"),
    )


def test_make_store_uses_qdrant_url_when_configured():
    store = make_store(_config(Path(".rag/qdrant"), qdrant_url="http://127.0.0.1:6333"))

    assert store.url == "http://127.0.0.1:6333"
    assert store.path is None


def test_make_store_falls_back_to_local_path(tmp_path: Path):
    db_path = tmp_path / "qdrant"
    store = make_store(_config(db_path))

    assert store.url is None
    assert store.path == db_path


def test_answer_skips_llm_when_top_score_is_below_min_score(monkeypatch, tmp_path: Path):
    low_score_results = [
        SearchResult(
            chunk=TextChunk(text="深圳路亚小程序活动报名页", metadata={"source": "agent.md"}),
            score=0.21,
        )
    ]

    monkeypatch.setattr("obsidian_rag.pipeline.search", lambda question, config, top_k: low_score_results)

    class FailingChatClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("LLM should not be called for low-score retrieval")

    monkeypatch.setattr("obsidian_rag.pipeline.OpenAIChatClient", FailingChatClient)

    response, results = answer("今天深圳天气怎么样", _config(tmp_path / "qdrant"), top_k=5)

    assert results == []
    assert "本地知识库没有足够相关资料" in response
    assert "0.21" in response
    assert "0.35" in response
