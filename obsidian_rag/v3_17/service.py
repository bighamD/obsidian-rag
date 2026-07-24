from __future__ import annotations

from importlib.metadata import version

from langchain_core.messages import AIMessage, HumanMessage

from obsidian_rag.console_api.schemas import (
    ConsoleConversationDeleteResponse,
    ConsoleConversationListResponse,
    ConsoleConversationResponse,
    ConsoleConversationSummary,
)
from obsidian_rag.core.schemas import MemorySnapshot, MemoryTurn
from obsidian_rag.v3_15.schemas import ApprovalDecisionInput, ApprovalListResponse
from obsidian_rag.v3_16.artifacts import project_artifacts, resolve_artifact
from obsidian_rag.v3_16.schemas import DeepAgentArtifactListResponse
from obsidian_rag.v3_17.context import SUMMARY_TRIGGER_FRACTION, memory_namespace
from obsidian_rag.v3_17.schemas import (
    DurableConversationDeleteResponse,
    DurableConversationListResponse,
    DurableHealthResponse,
    DurableRuntimeConfigResponse,
    DurableRuntimeContext,
    LongTermMemoryDeleteResponse,
    LongTermMemoryListResponse,
    LongTermMemoryPutRequest,
    MemoryAuditListResponse,
)


class DurableAgentLearningService:
    """V3.17 FastAPI/CLI 门面，聚合 Thread、Store、Summary、HITL 和 Artifact。"""

    def __init__(
        self,
        *,
        runtime,
        store,
        agent_factory,
        sandbox,
        memory_service,
        long_term_store,
        model_context_tokens: int,
    ):
        self.runtime = runtime
        self.store = store
        self.agent_factory = agent_factory
        self.sandbox = sandbox
        self.memory_service = memory_service
        self.long_term_store = long_term_store
        self.model_context_tokens = model_context_tokens

    def ask(self, request):
        return self.runtime.ask(request)

    def start_stream(self, request):
        return self.runtime.start_stream(request)

    def stream(self, run_id: str):
        return self.runtime.stream(run_id)

    def response(self, run_id: str):
        return self.runtime.get_response(run_id)

    def approval(self, run_id: str):
        return self.store.get_approval(run_id)

    def approvals(self, status: str | None, limit: int) -> ApprovalListResponse:
        return ApprovalListResponse(approvals=self.store.list_approvals(status=status, limit=limit))

    def resume(self, run_id: str, decision: ApprovalDecisionInput):
        return self.runtime.resume(run_id, decision)

    def start_resume_stream(self, run_id: str, decision: ApprovalDecisionInput):
        return self.runtime.start_resume_stream(run_id, decision)

    def recover(self, run_id: str):
        return self.runtime.recover(run_id)

    def start_recovery_stream(self, run_id: str):
        return self.runtime.start_recovery_stream(run_id)

    def artifacts(self, run_id: str) -> DeepAgentArtifactListResponse:
        return DeepAgentArtifactListResponse(run_id=run_id, artifacts=project_artifacts(self.sandbox, run_id))

    def artifact_path(self, artifact_id: str):
        return resolve_artifact(self.sandbox, self.store, artifact_id)

    def conversations(self, tenant_id: str, user_id: str, assistant_id: str, limit: int):
        return DurableConversationListResponse(
            conversations=self.store.list_conversations(tenant_id, user_id, assistant_id, limit)
        )

    def delete_conversation(self, conversation_id: str, tenant_id: str, user_id: str, assistant_id: str):
        return self.store.delete_conversation(conversation_id, tenant_id, user_id, assistant_id)

    def memories(self, tenant_id: str, user_id: str, assistant_id: str):
        context = _management_context(tenant_id, user_id, assistant_id)
        self.memory_service.ensure_profile(context)
        return LongTermMemoryListResponse(
            namespace=list(memory_namespace(context)),
            memories=self.memory_service.list(context),
        )

    def put_memory(self, request: LongTermMemoryPutRequest):
        context = _management_context(request.tenant_id, request.user_id, request.assistant_id)
        self.memory_service.ensure_profile(context)
        return self.memory_service.put(context, request, actor="user")

    def delete_memory(self, memory_id: str, tenant_id: str, user_id: str, assistant_id: str):
        context = _management_context(tenant_id, user_id, assistant_id)
        return LongTermMemoryDeleteResponse(
            memory_id=memory_id,
            deleted=self.memory_service.delete(context, memory_id, actor="user"),
        )

    def audits(self, tenant_id: str, user_id: str, assistant_id: str, limit: int):
        return MemoryAuditListResponse(
            audits=self.store.list_audits(tenant_id, user_id, assistant_id, limit)
        )

    def console_conversations(self, tenant_id: str, user_id: str, assistant_id: str, limit: int):
        conversations = self.store.list_conversations(tenant_id, user_id, assistant_id, limit)
        return ConsoleConversationListResponse(
            conversations=[
                ConsoleConversationSummary(
                    conversation_id=item.conversation_id,
                    title=item.title,
                    turn_count=item.turn_count,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in conversations
            ]
        )

    def console_conversation(self, conversation_id: str, window: int):
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise KeyError(f"Conversation not found: {conversation_id}")
        snapshot = self.agent_factory().thread_snapshot(conversation_id)
        messages = list(snapshot.values.get("messages", []))
        turns = _project_turns(conversation_id, messages)
        selected = turns[-window:] if window > 0 else []
        summary_event = snapshot.values.get("_summarization_event") or {}
        summary_message = summary_event.get("summary_message") if isinstance(summary_event, dict) else None
        summary_text = _message_text(getattr(summary_message, "content", "")) if summary_message else ""
        return ConsoleConversationResponse(
            conversation_id=conversation_id,
            memory_snapshot=MemorySnapshot(
                conversation_id=conversation_id,
                window=window,
                recent_turns=selected,
                total_turn_count=len(turns),
                loaded_turn_count=len(selected),
                omitted_turn_count=max(0, len(turns) - len(selected)),
                summary_text=summary_text,
            ),
        )

    def console_delete_conversation(self, conversation_id: str):
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            return ConsoleConversationDeleteResponse(
                conversation_id=conversation_id,
                deleted=False,
                deleted_turn_count=0,
            )
        result: DurableConversationDeleteResponse = self.delete_conversation(
            conversation_id,
            conversation.tenant_id,
            conversation.user_id,
            conversation.assistant_id,
        )
        return ConsoleConversationDeleteResponse(
            conversation_id=conversation_id,
            deleted=result.deleted,
            deleted_turn_count=conversation.turn_count if result.deleted else 0,
        )

    def runtime_config(self) -> DurableRuntimeConfigResponse:
        return DurableRuntimeConfigResponse(
            version="v3.17",
            framework=f"deepagents {version('deepagents')} on LangGraph",
            checkpointer_backend="LangGraph PostgresSaver: same-thread messages + HITL",
            long_term_store_backend="LangGraph PostgresStore + StoreBackend",
            backend_routes={
                "/artifacts/": "per-run Core Sandbox Workspace",
                "/context/": "per-thread StoreBackend for Summary offloading",
                "/memories/": "per-user StoreBackend for durable Memory",
            },
            memory_namespace=["tenant_id", "assistant_id", "user_id"],
            model_context_tokens=self.model_context_tokens,
            summary_trigger_fraction=SUMMARY_TRIGGER_FRACTION,
            conversation_memory_enabled=True,
            long_term_memory_enabled=True,
            endpoints={
                "ask": "/agent/ask",
                "stream": "/agent/ask/stream",
                "conversations": "/conversations",
                "memories": "/memories",
                "audits": "/memory-audits",
                "resume": "/approvals/{run_id}/resume",
                "recover": "/recoveries/{run_id}/retry",
                "artifact": "/artifacts/{artifact_id}/download",
            },
            sandbox=self.sandbox.runtime_status(),
        )

    def health(self) -> DurableHealthResponse:
        checkpoint_ready = self.agent_factory().checkpoint_ready()
        repository_ready = self.store.ready()
        try:
            self.long_term_store.search(("v3_17",), limit=1)
            long_term_store_ready = True
        except Exception:
            long_term_store_ready = False
        sandbox_available = self.sandbox.runtime_status().available
        return DurableHealthResponse(
            status="ok" if checkpoint_ready and repository_ready and long_term_store_ready else "degraded",
            version="v3.17",
            checkpoint_ready=checkpoint_ready,
            repository_ready=repository_ready,
            long_term_store_ready=long_term_store_ready,
            sandbox_available=sandbox_available,
        )


def _management_context(tenant_id: str, user_id: str, assistant_id: str) -> DurableRuntimeContext:
    return DurableRuntimeContext(
        tenant_id=tenant_id,
        user_id=user_id,
        assistant_id=assistant_id,
        conversation_id="",
        thread_id="",
        run_id="",
    )


def _project_turns(conversation_id: str, messages) -> list[MemoryTurn]:
    turns: list[MemoryTurn] = []
    pending_user: HumanMessage | None = None
    for message in messages:
        if isinstance(message, HumanMessage):
            pending_user = message
            continue
        if isinstance(message, AIMessage) and pending_user is not None and not message.tool_calls:
            turns.append(
                MemoryTurn(
                    turn_id=str(message.id or f"turn_{len(turns) + 1}"),
                    conversation_id=conversation_id,
                    user_message=_message_text(pending_user.content),
                    assistant_message=_message_text(message.content),
                    created_at="",
                )
            )
            pending_user = None
    return turns


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                parts.append(str(item.get("text") or ""))
        return "".join(parts)
    return str(content or "")
