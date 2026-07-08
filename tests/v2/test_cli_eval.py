from pathlib import Path

from obsidian_rag.cli import run_retrieval_eval
from obsidian_rag.config import RagConfig
from obsidian_rag.schema import SearchResult, TextChunk


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return [SearchResult(chunk=TextChunk(text="不建议清洗生鸡肉。", metadata={"source": "food.md"}), score=0.8)]


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
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.35,
        vault_path=None,
    )


def test_run_retrieval_eval_prints_summary_and_saves_report(tmp_path: Path, capsys):
    dataset_path = tmp_path / "eval_set.yaml"
    output_path = tmp_path / "report.json"
    dataset_path.write_text(
        """
examples:
  - id: chicken
    question: 鸡肉要洗吗
    expected_source_files:
      - food.md
""".strip(),
        encoding="utf-8",
    )

    run_retrieval_eval(
        dataset_path=dataset_path,
        config=_config(tmp_path),
        top_k=3,
        mode="hybrid",
        output_path=output_path,
        retrieval_service=FakeRetrievalService(),
    )

    output = capsys.readouterr().out
    assert "Examples: 1" in output
    assert "Hit rate@3: 1.0000" in output
    assert "MRR: 1.0000" in output
    assert f"Saved report: {output_path}" in output
    assert output_path.exists()
