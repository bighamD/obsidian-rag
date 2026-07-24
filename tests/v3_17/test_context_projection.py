from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from obsidian_rag.v3_17.agent import DurableDeepAgentService
from obsidian_rag.v3_17.schemas import DurableRuntimeContext


class EmptyMemoryService:
    def list(self, context):
        return []


def test_context_projection_reads_deepagents_summary_event():
    service = DurableDeepAgentService.__new__(DurableDeepAgentService)
    service.model_context_tokens = 4000
    service.memory_service = EmptyMemoryService()
    context = DurableRuntimeContext(
        tenant_id="tenant",
        user_id="user",
        assistant_id="assistant",
        conversation_id="conv",
        thread_id="thread",
        run_id="run",
    )
    snapshot = SimpleNamespace(
        values={
            "messages": [HumanMessage(content="old"), HumanMessage(content="new")],
            "_summarization_event": {
                "cutoff_index": 1,
                "summary_message": HumanMessage(content="已保留关键目标"),
                "file_path": "/context/conversation_history/thread.md",
            },
        }
    )

    projected = service._context_snapshot(snapshot, context)

    assert projected.summary.triggered is True
    assert projected.summary.cutoff_index == 1
    assert projected.summary.summary_text == "已保留关键目标"
    assert projected.exact_wire_prompt_available is False

