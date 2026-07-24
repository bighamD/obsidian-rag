from langgraph.store.memory import InMemoryStore

from obsidian_rag.v3_17.context import MEMORY_PROFILE_PATH, memory_namespace
from obsidian_rag.v3_17.memory import LongTermMemoryService, MemoryPolicy
from obsidian_rag.v3_17.schemas import DurableRuntimeContext, LongTermMemoryPutRequest


class FakeAuditStore:
    def __init__(self):
        self.records = []

    def add_audit(self, **kwargs):
        self.records.append(kwargs)


def context(user_id: str = "user_a") -> DurableRuntimeContext:
    return DurableRuntimeContext(
        tenant_id="tenant_a",
        user_id=user_id,
        assistant_id="assistant_a",
        conversation_id="conv_a",
        thread_id="thread_a",
        run_id="run_a",
    )


def test_memory_service_materializes_profile_and_audit():
    store = InMemoryStore()
    audits = FakeAuditStore()
    service = LongTermMemoryService(store, audits)
    runtime = context()

    service.ensure_profile(runtime)
    item = service.put(
        runtime,
        LongTermMemoryPutRequest(kind="preference", content="以后回答控制在100字以内"),
        actor="agent",
    )

    assert service.list(runtime)[0].memory_id == item.memory_id
    profile = store.get(memory_namespace(runtime), "/profile.md")
    assert profile is not None
    assert "100字以内" in profile.value["content"]
    assert audits.records[0]["operation"] == "create"
    assert MEMORY_PROFILE_PATH == "/memories/profile.md"


def test_memory_namespace_isolates_users():
    assert memory_namespace(context("user_a")) != memory_namespace(context("user_b"))


def test_memory_policy_rejects_secret():
    policy = MemoryPolicy()
    try:
        policy.validate("fact", "API_KEY=secret-value")
    except ValueError as exc:
        assert "Secret" in str(exc)
    else:
        raise AssertionError("secret must be rejected")

