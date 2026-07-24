from pathlib import Path

from obsidian_rag.cli import run_agent_ask
from obsidian_rag.config import RagConfig
from obsidian_rag.schema import SearchResult, TextChunk


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return [
            SearchResult(
                chunk=TextChunk(text="不建议清洗生鸡肉。", metadata={"source": "food.md"}),
                score=0.8,
            )
        ]


class FakeChatClient:
    def complete(self, messages):
        return "不建议清洗生鸡肉。"


def _config(tmp_path: Path) -> RagConfig:
    return RagConfig(
        api_key="test-key",
        base_url="http://127.0.0.1:8317/v1",
        chat_model="gpt-5.4-mini",
        embedding_model="qwen3-embedding:0.6b",
        embedding_dimensions=1024,
        embedding_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        qdrant_url=None,
        db_path=tmp_path / "qdrant",
        collection_name="obsidian_notes",
        min_score=0.35,
        vault_path=None,
    )


def test_run_agent_ask_prints_answer_and_trace(tmp_path: Path, capsys):
    run_agent_ask(
        question="生鸡肉要清洗吗？",
        config=_config(tmp_path),
        top_k=2,
        mode="hybrid",
        max_steps=1,
        retrieval_service=FakeRetrievalService(),
        chat_client=FakeChatClient(),
    )

    output = capsys.readouterr().out
    assert "不建议清洗生鸡肉。" in output
    assert "Trace:" in output
    assert "search_notes" in output


def test_run_agent_ask_no_search_does_not_require_llm_key(tmp_path: Path, capsys):
    config = _config(tmp_path)
    config = RagConfig(**{**config.__dict__, "api_key": ""})

    run_agent_ask(
        question="你好",
        config=config,
        top_k=2,
        mode="hybrid",
        max_steps=2,
        retrieval_service=FakeRetrievalService(),
    )

    output = capsys.readouterr().out
    assert "你好，我是本地知识库 RAG 助手" in output
    assert "decision=no_search" in output
