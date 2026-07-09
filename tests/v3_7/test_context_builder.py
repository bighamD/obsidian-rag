from obsidian_rag.v1.schemas import SearchHit
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_7.context import ContextBuilder
from obsidian_rag.v3_7.schemas import EvidenceCheckResult, StepResult


def _hit(chunk_id: str | None, source: str, score: float, text: str = "证据") -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        source=source,
        topic="食品安全",
        score=score,
        text_preview=text,
        metadata={"source": source, "chunk_id": chunk_id, "topic": "食品安全"},
    )


def test_context_builder_prioritizes_chunk_ids_and_tracks_exclusions():
    step = StepResult(
        step_id="s1",
        kind="search",
        tool_name="search_notes",
        query="生鸡肉 清洗",
        status="success",
        result_count=3,
        results=[
            _hit(None, "low.md", 0.99, "没有 chunk id 的高分证据"),
            _hit("KB-072", "food.md", 0.88, "不建议清洗生鸡肉，因为水花会造成交叉污染。"),
            _hit("KB-073", "clean.md", 0.76, "处理生肉后要洗手和清洁台面。"),
        ],
    )
    builder = ContextBuilder(max_chunks=2, token_budget=1200)

    bundle = builder.build(
        question="生鸡肉需要清洗吗",
        plan=Plan(goal="回答食品安全问题", steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")]),
        step_results=[step],
        retry_step_results=[],
        evidence_check=EvidenceCheckResult(is_sufficient=True, checked_step_ids=["s1"], reason="有证据。"),
    )

    assert [chunk.chunk_id for chunk in bundle.included_chunks] == ["KB-072", "KB-073"]
    assert bundle.excluded_chunks[0].source == "low.md"
    assert bundle.excluded_chunks[0].reason == "超过 max_chunks 或优先级较低"
    assert bundle.context_summary == "已选择 2 个 chunks，排除 1 个 chunks。"
    assert bundle.token_budget == 1200
    assert bundle.messages[0]["role"] == "system"
    assert "只能基于 ContextBundle 中的证据回答" in bundle.messages[0]["content"]
    assert "KB-072" in bundle.messages[1]["content"]
