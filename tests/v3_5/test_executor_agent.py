from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.v3_5.agent.service import AgentService
from obsidian_rag.v3_5.schemas import AgentAskRequest


class FakePlannerService:
    def __init__(self, plan: Plan):
        self._plan = plan
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        return PlanResponse(
            question=request.question,
            plan=self._plan,
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrievalService:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "filters": filters})
        return [
            SearchResult(
                chunk=TextChunk(
                    text=f"{query} 的本地知识库证据。",
                    metadata={"source": f"{query}.md", "chunk_id": f"KB-{len(self.calls):03d}", "topic": query},
                ),
                score=0.88,
            )
        ]


class FakeChatClient:
    def __init__(self, answer="综合答案"):
        self.answer = answer
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return self.answer


def test_executor_runs_search_steps_and_synthesizes_answer():
    plan = Plan(
        goal="整理食品安全建议",
        steps=[
            PlanStep(id="s1", kind="search", query="生鸡肉 清洗 交叉污染"),
            PlanStep(id="s2", kind="search", query="厨房 清洁 洗手"),
            PlanStep(id="s3", kind="synthesize", instruction="综合前两步证据回答", depends_on=["s1", "s2"]),
        ],
    )
    retrieval = FakeRetrievalService()
    chat = FakeChatClient(answer="基于多步证据的最终答案")
    service = AgentService(
        planner_service=FakePlannerService(plan),
        retrieval_service=retrieval,
        chat_client=chat,
    )

    response = service.ask(AgentAskRequest(question="总结生鸡肉和厨房清洁建议", top_k=5, mode="hybrid", max_steps=4))

    assert response.run_id.startswith("run_")
    assert response.answer == "基于多步证据的最终答案"
    assert response.used_retrieval is True
    assert response.graph_path == ["planner", "execute_steps", "synthesize_answer"]
    assert [result.step_id for result in response.step_results] == ["s1", "s2", "s3"]
    assert response.step_results[0].status == "success"
    assert response.step_results[0].tool_name == "search_notes"
    assert response.step_results[0].result_count == 1
    assert response.step_results[2].status == "success"
    assert response.step_results[2].tool_name == "synthesize"
    assert retrieval.calls == [
        {"query": "生鸡肉 清洗 交叉污染", "top_k": 5, "mode": "hybrid", "filters": None},
        {"query": "厨房 清洁 洗手", "top_k": 5, "mode": "hybrid", "filters": None},
    ]
    assert chat.messages


def test_executor_preserves_hybrid_rank_fields_in_step_results():
    plan = Plan(
        goal="检索食品安全资料",
        steps=[PlanStep(id="s1", kind="search", query="生鸡肉 清洗")],
    )
    retrieval = FakeRetrievalService()
    retrieval.search = lambda *args, **kwargs: [
        RankedSearchResult(
            chunk=TextChunk(
                text="不建议冲洗生鸡肉，因为水花会造成交叉污染。",
                metadata={"source": "food.md", "chunk_id": "KB-072", "topic": "不建议清洗生鸡肉"},
            ),
            score=0.03278688524590164,
            dense_rank=1,
            keyword_rank=2,
            dense_score=0.91,
            keyword_score=3.5,
            hybrid_score=0.03278688524590164,
        )
    ]
    service = AgentService(
        planner_service=FakePlannerService(plan),
        retrieval_service=retrieval,
        chat_client=FakeChatClient(),
    )

    response = service.ask(AgentAskRequest(question="生鸡肉还需要清洗下锅吗", mode="hybrid"))

    hit = response.step_results[0].results[0]
    assert hit.chunk_id == "KB-072"
    assert hit.dense_rank == 1
    assert hit.keyword_rank == 2
    assert hit.dense_score == 0.91
    assert hit.keyword_score == 3.5
    assert hit.hybrid_score == 0.03278688524590164


def test_executor_no_search_plan_does_not_call_retrieval():
    plan = Plan(
        goal="外部实时问题",
        steps=[
            PlanStep(id="s1", kind="no_search", instruction="这是实时天气问题，请查询天气服务。", reason="本地知识库无法回答。")
        ],
    )
    retrieval = FakeRetrievalService()
    service = AgentService(
        planner_service=FakePlannerService(plan),
        retrieval_service=retrieval,
        chat_client=FakeChatClient(),
    )

    response = service.ask(AgentAskRequest(question="今天深圳天气怎么样"))

    assert response.used_retrieval is False
    assert response.answer == "这是实时天气问题，请查询天气服务。"
    assert response.step_results[0].tool_name == "no_search"
    assert response.step_results[0].status == "skipped"
    assert retrieval.calls == []
