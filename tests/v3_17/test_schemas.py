from obsidian_rag.v3_17.schemas import DurableAgentAskRequest, DurableRuntimeContext


def test_ask_request_has_stable_scope_defaults():
    request = DurableAgentAskRequest(question="你好")
    assert request.tenant_id == "tenant_demo"
    assert request.user_id == "user_demo"
    assert request.assistant_id == "obsidian_rag"


def test_runtime_context_separates_thread_and_run():
    context = DurableRuntimeContext(
        tenant_id="tenant",
        user_id="user",
        assistant_id="assistant",
        conversation_id="conv",
        thread_id="thread-stable",
        run_id="run-once",
    )
    assert context.thread_id != context.run_id

