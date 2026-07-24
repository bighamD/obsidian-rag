from pathlib import Path

from obsidian_rag.cli import run_agent36_ask
from obsidian_rag.config import RagConfig
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_6.schemas import AgentAskResponse, AgentTraceStep, EvidenceCheckResult, StepResult


class FakeAgentService:
    def __init__(self):
        self.requests = []

    def ask(self, request):
        self.requests.append(request)
        return AgentAskResponse(
            run_id="run_cli",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["food.md"],
            plan=Plan(goal="执行并检查证据", steps=[PlanStep(id="s1", kind="search", query="厨房 清洁")]),
            step_results=[
                StepResult(
                    step_id="s1",
                    kind="search",
                    tool_name="search_notes",
                    query="厨房 清洁",
                    status="success",
                    result_count=0,
                )
            ],
            retry_step_results=[
                StepResult(
                    step_id="retry_s1_1",
                    kind="search",
                    tool_name="search_notes",
                    query="厨房 清洁 食品安全",
                    status="success",
                    result_count=1,
                    sources=["food.md"],
                )
            ],
            evidence_check=EvidenceCheckResult(
                is_sufficient=True,
                missing_points=[],
                suggested_queries=[],
                checked_step_ids=["s1"],
                retry_count=1,
                reason="retry 后 search step 已有证据。",
            ),
            graph_path=["planner", "execute_steps", "evidence_check", "retry_search", "evidence_check", "synthesize_answer"],
            trace=[
                AgentTraceStep(
                    node_name="retry_search",
                    step_type="retry",
                    query="厨房 清洁 食品安全",
                    result_count=1,
                    reason="补搜缺失证据。",
                )
            ],
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
        min_score=0.35,
        vault_path=None,
    )


def test_run_agent36_ask_prints_evidence_and_retry(tmp_path: Path, capsys):
    agent_service = FakeAgentService()

    run_agent36_ask(
        question="处理完生鸡肉厨房怎么清洁",
        config=_config(tmp_path),
        top_k=5,
        mode="hybrid",
        max_steps=4,
        filter_path="__not_exists__.md",
        agent_service=agent_service,
    )

    output = capsys.readouterr().out
    assert agent_service.requests[0].filters.path == "__not_exists__.md"
    assert "Run: run_cli" in output
    assert "Evidence check:" in output
    assert "sufficient=True | retry_count=1 | reason=retry 后 search step 已有证据。" in output
    assert "Retry step results:" in output
    assert "retry_s1_1 | search | tool=search_notes | status=success | query=厨房 清洁 食品安全 | results=1" in output
