from pathlib import Path

from obsidian_rag.cli import run_agent37_ask
from obsidian_rag.config import RagConfig
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_7.schemas import (
    AgentAskResponse,
    ContextBundle,
    ContextChunk,
    EvidenceCheckResult,
    StepResult,
)


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            run_id="run_cli",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["food.md"],
            plan=Plan(goal="构建上下文并回答", steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")]),
            step_results=[StepResult(step_id="s1", kind="search", tool_name="search_notes", query="生鸡肉 清洗", status="success", result_count=1)],
            retry_step_results=[],
            evidence_check=EvidenceCheckResult(is_sufficient=True, checked_step_ids=["s1"], reason="有证据。"),
            context_bundle=ContextBundle(
                messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
                included_chunks=[ContextChunk(step_id="s1", chunk_id="KB-072", source="food.md", score=0.88, text_preview="证据")],
                excluded_chunks=[],
                token_budget=4000,
                context_summary="已选择 1 个 chunks，排除 0 个 chunks。",
            ),
            graph_path=["planner", "execute_steps", "evidence_check", "build_context", "synthesize_answer"],
            trace=[],
        )


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


def test_run_agent37_ask_prints_context_bundle(tmp_path: Path, capsys):
    run_agent37_ask(
        question="生鸡肉需要清洗吗",
        config=_config(tmp_path),
        top_k=5,
        mode="hybrid",
        context_max_chunks=3,
        agent_service=FakeAgentService(),
    )

    output = capsys.readouterr().out
    assert "Run: run_cli" in output
    assert "Context bundle:" in output
    assert "已选择 1 个 chunks，排除 0 个 chunks。 | token_budget=4000" in output
    assert "included: s1 | KB-072 | food.md | score=0.8800" in output
