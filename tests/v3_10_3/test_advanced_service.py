from langchain_core.language_models.fake_chat_models import FakeListChatModel
import pytest

from obsidian_rag.schema import SearchResult, TextChunk
from obsidian_rag.v3_4.schemas import Plan, PlanResponse, PlanStep
from obsidian_rag.v3_8_1.schemas import MemorySnapshot, MemoryWriteResult
from obsidian_rag.v3_10_3.agent.service import AdvancedAgentService
from obsidian_rag.v3_10_3.schemas import AdvancedAskRequest


class FakePlannerService:
    def __init__(self, plan: Plan):
        self.plan_value = plan
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        return PlanResponse(
            question=request.question,
            plan=self.plan_value,
            graph_path=["build_prompt", "call_planner", "parse_plan"],
            trace=[],
        )


class FakeRetrievalService:
    def __init__(self, empty_initial: bool = False):
        self.empty_initial = empty_initial
        self.calls = []

    def search(self, query, top_k=5, mode="hybrid", filters=None):
        self.calls.append({"query": query, "top_k": top_k, "mode": mode, "filters": filters})
        if self.empty_initial and "使用方法 注意事项" not in query:
            return []
        return [
            SearchResult(
                chunk=TextChunk(
                    text=f"{query} 的知识库证据。",
                    metadata={"source": "food.md", "chunk_id": f"KB-{len(self.calls):03d}"},
                ),
                score=0.9,
            )
        ]


class FakeMemoryStore:
    def __init__(self):
        self.writes = []

    def load_snapshot(self, conversation_id: str, window: int = 3):
        return MemorySnapshot(conversation_id=conversation_id, window=window)

    def append_turn(self, conversation_id, user_message, assistant_message, sources, tool_calls):
        self.writes.append(
            {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "assistant_message": assistant_message,
                "sources": sources,
                "tool_calls": tool_calls,
            }
        )
        return MemoryWriteResult(
            conversation_id=conversation_id,
            turn_id=f"turn-{len(self.writes)}",
            saved=True,
        )


def _service(plan: Plan, retrieval: FakeRetrievalService | None = None):
    retrieval = retrieval or FakeRetrievalService()
    memory = FakeMemoryStore()
    service = AdvancedAgentService(
        retrieval_service=retrieval,
        planner_service=FakePlannerService(plan),
        chat_model=FakeListChatModel(responses=["流式综合答案"]),
        memory_store=memory,
    )
    return service, retrieval, memory


def test_send_retry_policy_messages_and_state_history_work_together():
    plan = Plan(
        goal="并行整理食品安全主题",
        steps=[
            PlanStep(id="s1", kind="search", query="生鸡肉处理"),
            PlanStep(id="s2", kind="search", query="厨房清洁"),
            PlanStep(id="s3", kind="synthesize", instruction="综合两类证据", depends_on=["s1", "s2"]),
        ],
    )
    service, retrieval, memory = _service(plan)
    request = AdvancedAskRequest(
        question="总结生鸡肉处理和厨房清洁建议",
        conversation_id="conv_advanced",
        thread_id="thread_advanced",
        simulate_transient_search_failure=True,
    )

    events = list(service.stream_events(request, run_id="run_advanced"))
    response = events[-1]["data"]["response"]

    assert response["parallel_task_count"] == 2
    assert {result["step_id"] for result in response["step_results"]} == {"s1", "s2"}
    assert all(count == 2 for count in response["node_retry_counts"].values())
    assert sum(event["name"] == "retry_policy" for event in events) == 2
    assert "".join(event["data"]["delta"] for event in events if event["name"] == "answer_delta") == "流式综合答案"
    assert response["planner_subgraph_path"][0] == "prepare_planner_input"
    assert response["graph_path"].count("evidence_check") == 1
    assert len(retrieval.calls) == 2
    assert memory.writes[0]["assistant_message"] == "流式综合答案"
    assert service.get_history("thread_advanced").entries
    assert service._attempts == {}


def test_evidence_retry_is_separate_from_retry_policy():
    plan = Plan(
        goal="补齐冷门主题证据",
        steps=[
            PlanStep(id="s1", kind="search", query="冷门食品安全主题"),
            PlanStep(id="s2", kind="synthesize", instruction="综合证据", depends_on=["s1"]),
        ],
    )
    retrieval = FakeRetrievalService(empty_initial=True)
    service, _, _ = _service(plan, retrieval)

    response = service.ask(
        AdvancedAskRequest(
            question="冷门食品安全主题怎么处理？",
            conversation_id="conv_business_retry",
            thread_id="thread_business_retry",
            max_retries=1,
        ),
        run_id="run_business_retry",
    )

    assert response.step_results[0].result_count == 0
    assert response.retry_step_results[0].result_count == 1
    assert response.graph_path.count("evidence_check") == 2
    assert "dispatch_retry" in response.graph_path
    assert response.evidence_check.is_sufficient is True
    assert all(count == 1 for count in response.node_retry_counts.values())


@pytest.mark.parametrize("kind,instruction", [("no_search", "直接回答"), ("clarify", "请补充问题范围")])
def test_non_search_plan_skips_send_and_evidence(kind: str, instruction: str):
    plan = Plan(goal="非检索分支", steps=[PlanStep(id="s1", kind=kind, instruction=instruction)])
    service, retrieval, _ = _service(plan)

    response = service.ask(
        AdvancedAskRequest(
            question="这个怎么处理？",
            conversation_id=f"conv_{kind}",
            thread_id=f"thread_{kind}",
        )
    )

    assert retrieval.calls == []
    assert response.used_retrieval is False
    assert response.parallel_task_count == 0
    assert "dispatch_search" not in response.graph_path
    assert "evidence_check" not in response.graph_path
