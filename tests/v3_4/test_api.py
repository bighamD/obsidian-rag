from fastapi.testclient import TestClient

from obsidian_rag.v3_4.app import app
from obsidian_rag.v3_4.dependencies import get_planner_service
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
                        reason="查询本地知识库中的生鸡肉处理资料。",
                    )
                ],
            ),
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[
                PlannerTraceStep(
                    node_name="parse_plan",
                    step_type="planner_output",
                    reason="LLM Planner 返回结构化计划。",
                    metadata={"step_count": 1},
                )
            ],
        )


def test_v3_4_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3.4"}


def test_v3_4_planner_plan_returns_plan_json():
    app.dependency_overrides[get_planner_service] = lambda: FakePlannerService()
    client = TestClient(app)

    try:
        response = client.post(
            "/planner/plan",
            json={"question": "生鸡肉需要清洗吗", "top_k": 5, "mode": "hybrid", "max_steps": 4},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["goal"] == "生成食品安全检索计划"
    assert payload["plan"]["steps"][0]["kind"] == "search"
    assert payload["graph_path"] == ["build_prompt", "call_planner", "parse_plan"]
    assert payload["trace"][0]["step_type"] == "planner_output"
