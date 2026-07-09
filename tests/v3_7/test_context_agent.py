from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.v3_7.agent.service import AgentService
from obsidian_rag.v3_7.schemas import AgentAskRequest


class FakePlannerService:
    def __init__(self, plan: Plan):
        self._plan = plan

    def plan(self, request):
        return PlanResponse(
            question=request.question,
            plan=self._plan,
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrievalService:
    def __init__(self, results):
        self.results = results

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        return self.results


class FakeChatClient:
    def __init__(self):
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return "基于 ContextBundle 的最终答案"


def _result(chunk_id: str | None, score: float):
    return SearchResult(
        chunk=TextChunk(
            text=f"{chunk_id or 'NO-ID'} 证据文本",
            metadata={"source": f"{chunk_id or 'no-id'}.md", "chunk_id": chunk_id, "topic": "食品安全"},
        ),
        score=score,
    )


def test_v3_7_builds_context_bundle_before_synthesis():
    plan = Plan(goal="回答食品安全问题", steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")])
    chat = FakeChatClient()
    service = AgentService(
        planner_service=FakePlannerService(plan),
        retrieval_service=FakeRetrievalService([_result(None, 0.99), _result("KB-072", 0.88)]),
        chat_client=chat,
    )

    response = service.ask(AgentAskRequest(question="生鸡肉需要清洗吗", mode="hybrid", context_max_chunks=1))

    assert response.answer == "基于 ContextBundle 的最终答案"
    assert response.context_bundle.included_chunks[0].chunk_id == "KB-072"
    assert response.context_bundle.excluded_chunks[0].chunk_id is None
    assert response.graph_path == ["planner", "execute_steps", "evidence_check", "build_context", "synthesize_answer"]
    assert "KB-072" in chat.messages[0][1]["content"]
