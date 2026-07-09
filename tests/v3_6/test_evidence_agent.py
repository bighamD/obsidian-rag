from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.v3_6.agent.service import AgentService
from obsidian_rag.v3_6.schemas import AgentAskRequest


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
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.calls = []

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "filters": filters})
        return self.results_by_query.get(query, [])


class FakeChatClient:
    def __init__(self, answer="综合答案"):
        self.answer = answer
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return self.answer


def _result(text="证据", chunk_id="KB-001", source="food.md"):
    return SearchResult(
        chunk=TextChunk(text=text, metadata={"source": source, "chunk_id": chunk_id, "topic": "食品安全"}),
        score=0.88,
    )


def test_v3_6_sufficient_evidence_skips_retry_and_synthesizes():
    plan = Plan(
        goal="回答食品安全问题",
        steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")],
    )
    retrieval = FakeRetrievalService({"生鸡肉 清洗": [_result()]})
    service = AgentService(
        planner_service=FakePlannerService(plan),
        retrieval_service=retrieval,
        chat_client=FakeChatClient(answer="不建议清洗生鸡肉。"),
    )

    response = service.ask(AgentAskRequest(question="生鸡肉需要清洗吗", mode="hybrid"))

    assert response.used_retrieval is True
    assert response.evidence_check.is_sufficient is True
    assert response.evidence_check.missing_points == []
    assert response.evidence_check.retry_count == 0
    assert response.graph_path == ["planner", "execute_steps", "evidence_check", "synthesize_answer"]
    assert [call["query"] for call in retrieval.calls] == ["生鸡肉 清洗"]


def test_v3_6_insufficient_step_triggers_one_retry_search():
    plan = Plan(
        goal="回答厨房清洁问题",
        steps=[PlanStep(id="s1", kind="search", query="厨房 清洁")],
    )
    retrieval = FakeRetrievalService(
        {
            "厨房 清洁": [],
            "厨房 清洁 食品安全": [_result(text="处理生肉后要清洁台面并洗手。", chunk_id="KB-073")],
        }
    )
    service = AgentService(
        planner_service=FakePlannerService(plan),
        retrieval_service=retrieval,
        chat_client=FakeChatClient(answer="处理生肉后要清洁台面并洗手。"),
    )

    response = service.ask(AgentAskRequest(question="处理完生鸡肉厨房怎么清洁", mode="hybrid"))

    assert response.evidence_check.is_sufficient is True
    assert response.evidence_check.retry_count == 1
    assert response.evidence_check.checked_step_ids == ["s1"]
    assert response.retry_step_results[0].query == "厨房 清洁 食品安全"
    assert response.retry_step_results[0].result_count == 1
    assert response.graph_path == [
        "planner",
        "execute_steps",
        "evidence_check",
        "retry_search",
        "evidence_check",
        "synthesize_answer",
    ]
    assert [call["query"] for call in retrieval.calls] == ["厨房 清洁", "厨房 清洁 食品安全"]
