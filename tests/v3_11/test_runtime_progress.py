from obsidian_rag.v3_10.runtime.store import InMemoryRunStore
from obsidian_rag.v3_10.schemas import RunRecord, RunTiming
from obsidian_rag.v3_11.runtime.service import SkillRuntimeService


class CapturingEventBus:
    def __init__(self):
        self.events = []

    def publish(self, run_id, name, status, detail, data=None):
        self.events.append((run_id, name, status, detail, data))


def test_v3_11_runtime_forwards_progress_through_event_bus():
    event_bus = CapturingEventBus()
    runtime = SkillRuntimeService(lambda: None, InMemoryRunStore(), event_bus)
    record = RunRecord(
        run_id="prod_progress",
        status="running",
        timing=RunTiming(started_at="2026-07-15T00:00:00Z"),
        events=[],
    )

    runtime._append_event(
        record,
        "progress",
        "running",
        "Agent 阶段 retrieval：running。",
        {"skill_agent": {"phase": "retrieval", "status": "running", "collection": "food_safety"}},
    )

    assert event_bus.events[0][1] == "progress"
    assert event_bus.events[0][4]["skill_agent"]["collection"] == "food_safety"


def test_v3_11_runtime_forwards_reasoning_without_run_history_growth():
    event_bus = CapturingEventBus()
    runtime = SkillRuntimeService(lambda: None, InMemoryRunStore(), event_bus)
    record = RunRecord(
        run_id="prod_reasoning",
        status="running",
        timing=RunTiming(started_at="2026-07-15T00:00:00Z"),
        events=[],
    )

    runtime._publish_record_event(
        record,
        "reasoning_delta",
        "running",
        "Answer LLM 产生学习调试 reasoning 增量。",
        {"message_id": "msg_test", "sequence": 1, "delta": "先分析问题。"},
    )

    assert record.events == []
    assert event_bus.events[0][1] == "reasoning_delta"
