from pathlib import Path

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v2.evaluation.dataset import EvalDataset, EvalExample
from obsidian_rag.v2.evaluation.retrieval import RetrievalEvaluator


class FakeRetrievalService:
    def search(self, query, top_k=5, mode="hybrid", filters=None):
        if "鸡肉" in query:
            return [
                SearchResult(
                    chunk=TextChunk(
                        text="不建议清洗生鸡肉。",
                        metadata={"source": "food.md", "chunk_id": "KB-072"},
                    ),
                    score=0.9,
                ),
                SearchResult(
                    chunk=TextChunk(text="其他资料。", metadata={"source": "other.md"}),
                    score=0.3,
                ),
            ]
        return [SearchResult(chunk=TextChunk(text="无关资料。", metadata={"source": "other.md"}), score=0.2)]


def test_retrieval_evaluator_builds_report_and_saves_json(tmp_path: Path):
    dataset = EvalDataset(
        examples=[
            EvalExample(id="chicken", question="鸡肉要洗吗", expected_source_files=["food.md"]),
            EvalExample(id="rice", question="米饭能放多久", expected_source_files=["rice.md"]),
        ]
    )
    output_path = tmp_path / "report.json"
    evaluator = RetrievalEvaluator(FakeRetrievalService())

    report = evaluator.evaluate_dataset(dataset, top_k=2, mode="hybrid", output_path=output_path)

    assert report.summary.example_count == 2
    assert report.summary.hit_rate_at_k == 0.5
    assert report.examples[0].hit is True
    assert report.examples[0].retrieved_source_files == ["food.md", "other.md"]
    assert report.examples[1].hit is False
    assert output_path.exists()
    assert '"hit_rate_at_k": 0.5' in output_path.read_text(encoding="utf-8")
