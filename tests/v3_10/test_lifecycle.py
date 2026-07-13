from obsidian_rag.v3_10.runtime.lifecycle import AgentRuntimeService
from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import ProductionAskRequest
from tests.v3_9.helpers import FakeAgentService


def test_runtime_service_records_success_metrics_and_tool_summary():
    store = InMemoryRunStore()
    service = AgentRuntimeService(agent_service=FakeAgentService(), run_store=store)

    response = service.ask(ProductionAskRequest(question="生鸡肉要不要洗？", conversation_id="conv_runtime"))

    assert response.run.status == "succeeded"
    assert response.run.agent_run_id == "run_eval"
    assert response.run.conversation_id == "conv_runtime"
    assert response.run.timing.duration_ms is not None
    assert response.run.metrics is not None
    assert response.run.metrics.retrieval_result_count == 1
    assert response.run.metrics.tool_summaries[0].model_dump() == {
        "tool_name": "search_notes",
        "call_count": 1,
        "success_count": 1,
        "failed_count": 0,
        "skipped_count": 0,
        "result_count": 1,
    }
    assert [event.name for event in response.run.events] == ["run_queued", "run_started", "run_succeeded"]
    assert store.get(response.run.run_id) == response.run


class FailingAgentService:
    def ask(self, request):
        raise ConnectionError("LLM service unavailable")


def test_runtime_service_returns_failed_run_without_raw_traceback():
    service = AgentRuntimeService(agent_service=FailingAgentService(), run_store=InMemoryRunStore())

    response = service.ask(ProductionAskRequest(question="生鸡肉要不要洗？"))

    assert response.agent_response is None
    assert response.run.status == "failed"
    assert response.run.error is not None
    assert response.run.error.error_type == "ConnectionError"
    assert response.run.error.message == "LLM service unavailable"
    assert [event.name for event in response.run.events] == ["run_queued", "run_started", "run_failed"]


def test_in_memory_run_store_keeps_most_recent_records_only():
    store = InMemoryRunStore(limit=2)
    service = AgentRuntimeService(agent_service=FakeAgentService(), run_store=store)

    first = service.ask(ProductionAskRequest(question="问题一")).run
    second = service.ask(ProductionAskRequest(question="问题二")).run
    third = service.ask(ProductionAskRequest(question="问题三")).run

    assert store.get(first.run_id) is None
    assert [record.run_id for record in store.list_recent()] == [third.run_id, second.run_id]
