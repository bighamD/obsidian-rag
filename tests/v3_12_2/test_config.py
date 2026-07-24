from obsidian_rag.config import load_config


def test_rerank_environment_configuration(monkeypatch):
    monkeypatch.setenv("RAG_RERANK_ENABLED", "true")
    monkeypatch.setenv("RAG_RERANK_PROVIDER", "fake")
    monkeypatch.setenv("RAG_RERANK_MODEL", "test-reranker")
    monkeypatch.setenv("RAG_RERANK_CANDIDATES", "12")
    monkeypatch.setenv("RAG_RERANK_TOP_K", "4")
    monkeypatch.setenv("RAG_RERANK_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("RAG_RERANK_DEVICE", "cpu")
    monkeypatch.setenv("RAG_RERANK_BATCH_SIZE", "3")

    config = load_config()

    assert config.rerank_enabled is True
    assert config.rerank_provider == "fake"
    assert config.rerank_model == "test-reranker"
    assert config.rerank_candidates == 12
    assert config.rerank_top_k == 4
    assert config.rerank_timeout_seconds == 2.5
    assert config.rerank_device == "cpu"
    assert config.rerank_batch_size == 3
