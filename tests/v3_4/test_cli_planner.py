from pathlib import Path

from obsidian_rag.cli import run_agent34_plan
from obsidian_rag.config import RagConfig
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep, PlannerTraceStep


class FakePlannerService:
    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=Plan(
                goal="生成食品安全检索计划",
                steps=[
                    PlanStep(
                        id="s1",
                        kind="search",
                        query="生鸡肉 清洗 交叉污染",
                        reason="查询生鸡肉处理资料。",
                    ),
                    PlanStep(
                        id="s2",
                        kind="synthesize",
                        instruction="综合检索结果回答。",
                        depends_on=["s1"],
                    ),
                ],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[
                PlannerTraceStep(
                    node_name="parse_plan",
                    step_type="planner_output",
                    reason="LLM Planner 返回结构化计划。",
                    metadata={"step_count": 2},
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


def test_run_agent34_plan_prints_plan_and_trace(tmp_path: Path, capsys):
    run_agent34_plan(
        question="生鸡肉需要清洗吗",
        config=_config(tmp_path),
        top_k=5,
        mode="hybrid",
        max_steps=4,
        planner_service=FakePlannerService(),
    )

    output = capsys.readouterr().out
    assert "Goal: 生成食品安全检索计划" in output
    assert "s1 | search | query=生鸡肉 清洗 交叉污染" in output
    assert "Graph path:" in output
    assert "build_prompt -> call_planner -> parse_plan" in output
    assert "Trace:" in output
