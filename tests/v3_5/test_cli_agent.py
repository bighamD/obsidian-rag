from pathlib import Path

from obsidian_rag.cli import run_agent35_ask
from obsidian_rag.config import RagConfig
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_5.schemas import AgentAskResponse, AgentTraceStep, StepResult


class FakeAgentService:
    def ask(self, request):
        return AgentAskResponse(
            run_id="run_cli",
            question=request.question,
            answer="最终答案",
            used_retrieval=True,
            sources=["KB-001：food.md"],
            plan=Plan(goal="执行食品安全计划", steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")]),
            step_results=[
                StepResult(
                    step_id="s1",
                    kind="search",
                    tool_name="search_notes",
                    query="生鸡肉 清洗",
                    status="success",
                    result_count=1,
                    sources=["KB-001：food.md"],
                )
            ],
            graph_path=["planner", "execute_steps", "synthesize_answer"],
            trace=[
                AgentTraceStep(
                    node_name="execute_steps",
                    step_type="tool_result",
                    step_id="s1",
                    tool_name="search_notes",
                    query="生鸡肉 清洗",
                    result_count=1,
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
        chunk_size=1200,
        chunk_overlap=150,
        min_score=0.35,
        vault_path=None,
    )


def test_run_agent35_ask_prints_step_results(tmp_path: Path, capsys):
    run_agent35_ask(
        question="生鸡肉需要清洗吗",
        config=_config(tmp_path),
        top_k=5,
        mode="hybrid",
        max_steps=4,
        agent_service=FakeAgentService(),
    )

    output = capsys.readouterr().out
    assert "Run: run_cli" in output
    assert "最终答案" in output
    assert "Step results:" in output
    assert "s1 | search | tool=search_notes | status=success | query=生鸡肉 清洗 | results=1" in output
    assert "planner -> execute_steps -> synthesize_answer" in output
