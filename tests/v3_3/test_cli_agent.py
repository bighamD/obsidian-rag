from pathlib import Path

from obsidian_rag.cli import run_agent33_ask
from obsidian_rag.config import RagConfig
from obsidian_rag.llm import ToolCall, ToolCallingResponse
from obsidian_rag.schema import SearchResult, TextChunk


class FakeToolChatClient:
    def complete_with_tools(self, messages, tools):
        return ToolCallingResponse(
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_notes",
                    arguments={"query": "生鸡肉 清洗 交叉污染", "top_k": 2},
                )
            ]
        )

    def complete(self, messages):
        return "基于资料：不建议清洗生鸡肉。"


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return [
            SearchResult(
                chunk=TextChunk(text="不建议清洗生鸡肉。", metadata={"source": "food.md"}),
                score=0.8,
            )
        ]


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


def test_run_agent33_ask_prints_graph_path_and_trace(tmp_path: Path, capsys):
    run_agent33_ask(
        question="生鸡肉还需要清洗下锅吗",
        config=_config(tmp_path),
        top_k=2,
        mode="hybrid",
        max_steps=1,
        retrieval_service=FakeRetrievalService(),
        chat_client=FakeToolChatClient(),
    )

    output = capsys.readouterr().out
    assert "基于资料：不建议清洗生鸡肉。" in output
    assert "Graph path:" in output
    assert "select_tool -> search_notes -> evidence_check -> answer" in output
    assert "Trace:" in output
