from fastapi.testclient import TestClient

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3.app import app
from obsidian_rag.v3.dependencies import get_agent_service


class FakeAgentService:
    def ask(self, request):
        from obsidian_rag.v3.schemas import AgentAskResponse, AgentTraceStep

        return AgentAskResponse(
            question=request.question,
            answer="测试答案",
            used_retrieval=True,
            sources=["food.md"],
            trace=[
                AgentTraceStep(step_type="decision", decision="search", reason="需要本地知识库"),
                AgentTraceStep(
                    step_type="search",
                    tool_name="search_notes",
                    query=request.question,
                    result_count=1,
                    results=[
                        {
                            "chunk_id": "KB-072",
                            "source": "food.md",
                            "topic": "不建议清洗生鸡肉",
                            "score": 0.9,
                            "text_preview": "不建议清洗生鸡肉。",
                            "metadata": {"source": "food.md"},
                        }
                    ],
                ),
                AgentTraceStep(step_type="answer", reason="基于检索结果生成答案"),
            ],
        )


def test_v3_health_returns_json_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v3"}


def test_agent_ask_returns_json_trace():
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    try:
        response = client.post(
            "/agent/ask",
            json={"question": "生鸡肉要清洗吗？", "top_k": 3, "mode": "hybrid", "max_steps": 2},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "测试答案"
    assert payload["used_retrieval"] is True
    assert payload["sources"] == ["food.md"]
    assert payload["trace"][1]["tool_name"] == "search_notes"
    assert payload["trace"][1]["results"][0]["chunk_id"] == "KB-072"
