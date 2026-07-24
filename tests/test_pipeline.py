from pathlib import Path
from dataclasses import replace

from obsidian_rag.config import RagConfig
from obsidian_rag.pipeline import answer, ingest_path, make_store
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


def test_ingest_path_always_uses_docling(monkeypatch, tmp_path: Path):
    chunk = TextChunk(text="Docling chunk", metadata={"source": "note.md"})
    captured = {}

    class FakeIngestion:
        def convert_and_chunk_path(self, path):
            captured["path"] = path
            return type("Batch", (), {"errors": [], "conversions": [object()], "chunks": [chunk]})()

    class FakeEmbeddings:
        def embed_texts(self, texts):
            captured["texts"] = texts
            return [[0.0] * 1024]

    class FakeStore:
        def ensure_collection(self, recreate=False):
            captured["recreate"] = recreate

        def upsert(self, chunks, vectors):
            captured["chunks"] = chunks

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("obsidian_rag.pipeline.make_docling_ingestion", lambda config: FakeIngestion())
    monkeypatch.setattr("obsidian_rag.pipeline.make_embedding_client", lambda config: FakeEmbeddings())
    monkeypatch.setattr("obsidian_rag.pipeline.make_store", lambda config: FakeStore())
    monkeypatch.setattr("obsidian_rag.pipeline._write_keyword_index", lambda *args, **kwargs: None)

    config = replace(_config(tmp_path / "qdrant"), chunk_strategy="docling_hybrid")
    assert ingest_path(tmp_path, config, recreate=True) == (1, 1)
    assert captured == {
        "path": tmp_path,
        "texts": ["Docling chunk"],
        "recreate": True,
        "chunks": [chunk],
        "closed": True,
    }


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
