from obsidian_rag.v1.schemas import SearchHit
from obsidian_rag.v3_4.schemas import Plan, PlanStep
from obsidian_rag.v3_8_1.schemas import (
    AgentAskRequest,
    AgentAskResponse,
    ContextBundle,
    EvidenceCheckResult,
    MemoryCompactionResult,
    MemorySnapshot,
    MemoryWriteResult,
    StepResult,
)
from obsidian_rag.v3_9.evaluation.evaluator import AgentEvaluator
from obsidian_rag.v3_9.schemas import AgentEvalCase, AgentEvalExpectation


class FakeAgentService:
    def __init__(self, response: AgentAskResponse):
        self.response = response
        self.requests = []

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        self.requests.append(request)
        return self.response


def _agent_response(*, used_retrieval: bool = True, tool_name: str | None = "search_notes") -> AgentAskResponse:
    results = [
        SearchHit(
            chunk_id="KB-072",
            source="food.md",
            topic="生鸡肉清洗",
            score=0.9,
            text_preview="不建议清洗生鸡肉，以免交叉污染。",
            metadata={"chunk_id": "KB-072", "source": "food.md"},
        )
    ]
    return AgentAskResponse(
        run_id="run_eval",
        conversation_id="conv_eval",
        question="生鸡肉要不要洗？",
        answer="不建议清洗生鸡肉，因为水花可能造成交叉污染。",
        used_retrieval=used_retrieval,
        sources=["food.md"],
        plan=Plan(
            goal="回答生鸡肉清洗问题",
            steps=[
                PlanStep(id="s1", kind="search", query="生鸡肉 清洗 交叉污染"),
                PlanStep(id="s2", kind="synthesize", instruction="综合答案", depends_on=["s1"]),
            ],
        ),
        step_results=[
            StepResult(
                step_id="s1",
                kind="search",
                tool_name=tool_name,
                query="生鸡肉 清洗 交叉污染",
                status="success",
                result_count=len(results),
                results=results,
                sources=["food.md"],
            )
        ],
        retry_step_results=[],
        evidence_check=EvidenceCheckResult(is_sufficient=True, reason="检索到证据。"),
        context_bundle=ContextBundle(
            messages=[{"role": "system", "content": "system"}, {"role": "user", "content": "context"}],
            token_budget=4000,
            context_summary="已构建上下文。",
        ),
        memory_snapshot=MemorySnapshot(conversation_id="conv_eval", window=3),
        memory_compaction=MemoryCompactionResult(conversation_id="conv_eval", reason="未达到压缩阈值。"),
        memory_write=MemoryWriteResult(conversation_id="conv_eval", turn_id="turn_eval", saved=True),
        graph_path=["planner", "execute_steps", "save_memory"],
        trace=[],
    )


def test_agent_evaluator_scores_all_expected_agent_behaviors():
    service = FakeAgentService(_agent_response())
    evaluator = AgentEvaluator(service)
    case = AgentEvalCase(
        id="chicken-wash",
        request=AgentAskRequest(question="生鸡肉要不要洗？"),
        expect=AgentEvalExpectation(
            should_retrieve=True,
            required_step_kinds=["search", "synthesize"],
            expected_tools=["search_notes"],
            expected_chunk_ids=["KB-072"],
            expected_source_files=["food.md"],
            evidence_sufficient=True,
            expected_answer_points=["不建议清洗生鸡肉", "交叉污染"],
        ),
    )

    report = evaluator.evaluate_case(case)

    assert service.requests == [case.request]
    assert report.passed is True
    assert report.score == 1.0
    assert [check.name for check in report.checks] == [
        "routing",
        "plan",
        "tools",
        "retrieval_chunks",
        "retrieval_sources",
        "evidence",
        "answer",
    ]
    assert all(check.passed for check in report.checks)


def test_agent_evaluator_reports_routing_and_tool_failures_separately():
    evaluator = AgentEvaluator(FakeAgentService(_agent_response(used_retrieval=True, tool_name="search_notes")))
    case = AgentEvalCase(
        id="weather-no-search",
        request=AgentAskRequest(question="今天深圳天气怎么样？"),
        expect=AgentEvalExpectation(should_retrieve=False, expected_tools=[]),
    )

    report = evaluator.evaluate_case(case)

    assert report.passed is False
    assert report.score == 0.0
    failures = {check.name: check for check in report.checks if not check.passed}
    assert failures["routing"].actual is True
    assert failures["tools"].actual == ["search_notes"]
