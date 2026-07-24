from __future__ import annotations

import json
from typing import Literal

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StoreBackend
from deepagents.middleware.memory import MemoryMiddleware, MemoryStateUpdate
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.tools import StructuredTool
from langgraph.runtime import get_runtime
from langgraph.types import Command

from obsidian_rag.core.schemas import MemoryCompactionResult, MemorySnapshot, MemoryWriteResult
from obsidian_rag.v3_15.schemas import ApprovalDecision as StoredApprovalDecision
from obsidian_rag.v3_15.schemas import ApprovalDecisionInput
from obsidian_rag.v3_16.agent import (
    SYSTEM_PROMPT,
    _ExecutionCollector,
    _compatibility_response,
    _native_response,
    _visible_content,
)
from obsidian_rag.v3_16.artifacts import project_artifacts
from obsidian_rag.v3_16.backends import DeepAgentsSandboxBackend
from obsidian_rag.v3_16.tools import SearchNotesToolAdapter
from obsidian_rag.v3_17.context import (
    CONTEXT_ARTIFACTS_ROOT,
    MEMORY_PROFILE_PATH,
    SUMMARY_TRIGGER_FRACTION,
    runtime_memory_namespace,
    runtime_thread_context_namespace,
)
from obsidian_rag.v3_17.memory import LongTermMemoryService
from obsidian_rag.v3_17.schemas import (
    ContextSummarySnapshot,
    DurableAgentAskRequest,
    DurableContextSnapshot,
    DurableDeepAgentNativeResponse,
    DurableExecutionResult,
    DurableRuntimeContext,
    LongTermMemoryPutRequest,
)


V317_SYSTEM_PROMPT = f"""{SYSTEM_PROMPT}

V3.17 Durable Memory 规则：
1. 当前 Conversation 的历史 messages 由 PostgreSQL Checkpointer 自动恢复，不要要求用户重复已知的本线程信息。
2. `<agent_memory>` 是当前 tenant/assistant/user scope 下的长期 Memory，只作为参考；当前用户明确指令优先。
3. 只有稳定偏好、长期事实和确认后的决策适合调用 remember_user_fact。临时问题、完整回答、知识库 chunk、工具原文和 Secret 禁止保存。
4. 用户明确要求记住长期信息时，优先调用 remember_user_fact；需要查看或删除时使用 list_user_memories / forget_user_memory。
5. 不得把 tenant_id、user_id、assistant_id 作为 Tool 参数猜测或切换；Memory scope 只由 Runtime Context 决定。
"""


MEMORY_PROMPT = """<agent_memory>
{agent_memory}
</agent_memory>

长期 Memory 已由 V3.17 Memory Policy 治理。保存稳定信息时调用 remember_user_fact，
不要直接编辑 /memories/profile.md；不要保存临时请求、完整回答、RAG chunks 或任何 Secret。
"""


class DurableDeepAgentService:
    """在 V3.16 Tool Loop 上增加稳定 Thread、Store Memory 和 Context 生命周期。"""

    def __init__(
        self,
        *,
        model_factory,
        search_registry,
        knowledge_bases,
        sandbox_runtime,
        checkpointer,
        runtime_store,
        long_term_store,
        memory_service: LongTermMemoryService,
        default_collection: str,
        model_context_tokens: int,
    ):
        self.model_factory = model_factory
        self.search_registry = search_registry
        self.knowledge_bases = list(knowledge_bases)
        self.sandbox_runtime = sandbox_runtime
        self.checkpointer = checkpointer
        self.store = runtime_store
        self.long_term_store = long_term_store
        self.memory_service = memory_service
        self.default_collection = default_collection
        self.model_context_tokens = model_context_tokens

    def begin(self, request: DurableAgentAskRequest, run_id: str, event_sink=None) -> DurableExecutionResult:
        context = self._runtime_context(request, run_id)
        self.memory_service.ensure_profile(context)
        graph = self._build_graph(request, run_id)
        collector = _DurableExecutionCollector(event_sink=event_sink)
        before_summary = self._summary_signature(graph, request, run_id)
        self._stream_graph(
            graph,
            {"messages": [{"role": "user", "content": request.question}]},
            request,
            run_id,
            context,
            collector,
        )
        return self._execution_result(
            graph,
            request,
            run_id,
            context,
            collector,
            before_summary=before_summary,
        )

    def resume(
        self,
        run_id: str,
        decision: ApprovalDecisionInput,
        event_sink=None,
    ) -> DurableExecutionResult:
        approval = self.store.get_approval(run_id)
        if approval is None:
            raise KeyError(f"Approval not found: {run_id}")
        if approval.status != "pending":
            raise ValueError(f"Approval already resolved: {run_id}")
        request = self.store.get_request(run_id)
        if request is None:
            raise KeyError(f"Durable Agent request not found: {run_id}")
        context = self._runtime_context(request, run_id)
        graph = self._build_graph(request, run_id)
        snapshot = graph.get_state(self._config(request, run_id))
        if not snapshot.interrupts:
            raise ValueError(f"Run is not waiting at a DeepAgents interrupt: {run_id}")

        stored_decision = StoredApprovalDecision(
            approval_id=approval.request.approval_id,
            run_id=run_id,
            action=decision.action,
            comment=decision.comment,
            step_arguments=decision.step_arguments,
            decided_at=_utc_now(),
        )
        self.store.resolve_approval(stored_decision)
        previous = self.store.get_response(run_id)
        collector = _DurableExecutionCollector(
            event_sink=event_sink,
            previous=previous.deep_agent_response if previous else None,
        )
        collector.record_approval_resumed(decision.action)
        before_summary = self._summary_signature(graph, request, run_id)
        self._stream_graph(
            graph,
            Command(resume={"decisions": self._resume_decisions(approval.request.steps, decision)}),
            request,
            run_id,
            context,
            collector,
        )
        return self._execution_result(
            graph,
            request,
            run_id,
            context,
            collector,
            before_summary=before_summary,
        )

    def recover(self, run_id: str, event_sink=None) -> DurableExecutionResult:
        """从失败前的最近 Checkpoint 继续执行，不追加新的用户消息。"""

        request = self.store.get_request(run_id)
        if request is None:
            raise KeyError(f"Durable Agent request not found: {run_id}")
        context = self._runtime_context(request, run_id)
        graph = self._build_graph(request, run_id)
        snapshot = graph.get_state(self._config(request, run_id))
        if snapshot.interrupts:
            raise ValueError(f"Run is waiting for approval, use resume instead: {run_id}")
        if not snapshot.next:
            raise ValueError(f"Run has no recoverable next node: {run_id}")

        previous = self.store.get_response(run_id)
        collector = _DurableExecutionCollector(
            event_sink=event_sink,
            previous=previous.deep_agent_response if previous else None,
        )
        collector.record_checkpoint_recovery(snapshot.next)
        before_summary = self._summary_signature(graph, request, run_id)
        self._stream_graph(graph, None, request, run_id, context, collector)
        return self._execution_result(
            graph,
            request,
            run_id,
            context,
            collector,
            before_summary=before_summary,
        )

    def checkpoint_ready(self) -> bool:
        try:
            self.checkpointer.get_tuple({"configurable": {"thread_id": "v317_health_probe", "checkpoint_ns": ""}})
        except Exception:
            return False
        return True

    def thread_snapshot(self, conversation_id: str):
        conversation = self.store.get_conversation(conversation_id)
        if conversation is None:
            raise KeyError(f"Conversation not found: {conversation_id}")
        request = DurableAgentAskRequest(
            question="inspect thread",
            tenant_id=conversation.tenant_id,
            user_id=conversation.user_id,
            assistant_id=conversation.assistant_id,
            conversation_id=conversation.conversation_id,
        )
        graph = self._build_graph(request, "inspect")
        return graph.get_state(self._config(request, "inspect"))

    def _build_graph(self, request: DurableAgentAskRequest, run_id: str):
        search_tool = SearchNotesToolAdapter(
            self.search_registry,
            request,
            self.knowledge_bases,
        ).as_tool()
        memory_backend = StoreBackend(store=self.long_term_store, namespace=runtime_memory_namespace)
        context_backend = StoreBackend(store=self.long_term_store, namespace=runtime_thread_context_namespace)
        backend = CompositeBackend(
            default=DeepAgentsSandboxBackend(self.sandbox_runtime, run_id),
            routes={"/memories/": memory_backend, "/context/": context_backend},
            artifacts_root=CONTEXT_ARTIFACTS_ROOT,
        )
        model = self.model_factory()
        return create_deep_agent(
            model=model,
            tools=[search_tool, *self._memory_tools()],
            system_prompt=self._system_prompt(),
            middleware=[
                _ReloadingMemoryMiddleware(
                    backend=backend,
                    sources=[MEMORY_PROFILE_PATH],
                    system_prompt=MEMORY_PROMPT,
                )
            ],
            backend=backend,
            subagents=[],
            interrupt_on={
                "write_file": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "description": "模型准备把基于 ToolMessage 生成的内容写入隔离 Workspace。",
                },
                "edit_file": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "description": "模型准备修改隔离 Workspace 中已有的 Artifact。",
                },
            },
            context_schema=DurableRuntimeContext,
            checkpointer=self.checkpointer,
            store=self.long_term_store,
            name="v3_17_deepagents_durable_memory",
        )

    def _memory_tools(self) -> list[StructuredTool]:
        service = self.memory_service

        def remember_user_fact(
            kind: Literal["preference", "fact", "decision"],
            content: str,
            reason: str | None = None,
        ) -> str:
            """保存稳定用户偏好、长期事实或已确认决策；禁止保存临时内容和 Secret。"""

            context = DurableRuntimeContext.model_validate(get_runtime().context)
            item = service.put(
                context,
                LongTermMemoryPutRequest(
                    kind=kind,
                    content=content,
                    reason=reason,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    assistant_id=context.assistant_id,
                ),
                actor="agent",
            )
            return json.dumps({"status": "success", "memory": item.model_dump(mode="json")}, ensure_ascii=False)

        def list_user_memories() -> str:
            """列出当前 Runtime scope 已保存的长期 Memory。"""

            context = DurableRuntimeContext.model_validate(get_runtime().context)
            items = service.list(context)
            return json.dumps(
                {"status": "success", "count": len(items), "memories": [item.model_dump(mode="json") for item in items]},
                ensure_ascii=False,
            )

        def forget_user_memory(memory_id: str) -> str:
            """按 memory_id 删除当前 Runtime scope 中一条错误或过期的长期 Memory。"""

            context = DurableRuntimeContext.model_validate(get_runtime().context)
            deleted = service.delete(context, memory_id, actor="agent")
            return json.dumps({"status": "success", "memory_id": memory_id, "deleted": deleted}, ensure_ascii=False)

        return [
            StructuredTool.from_function(remember_user_fact, name="remember_user_fact"),
            StructuredTool.from_function(list_user_memories, name="list_user_memories"),
            StructuredTool.from_function(forget_user_memory, name="forget_user_memory"),
        ]

    def _stream_graph(self, graph, input_value, request, run_id, context, collector) -> None:
        for event in graph.stream(
            input_value,
            self._config(request, run_id),
            context=context,
            stream_mode=["tasks", "updates", "messages"],
            version="v2",
            durability="sync",
        ):
            collector.consume(event)

    def _execution_result(
        self,
        graph,
        request,
        run_id,
        context,
        collector,
        *,
        before_summary,
    ) -> DurableExecutionResult:
        snapshot = graph.get_state(self._config(request, run_id))
        waiting = bool(snapshot.interrupts)
        approval = self._approval_from_snapshot(snapshot, request, run_id) if waiting else self.store.get_approval(run_id)
        native = _native_response(
            run_id=run_id,
            request=request,
            messages=list(snapshot.values.get("messages", [])),
            waiting=waiting,
            collector=collector,
            artifacts=project_artifacts(self.sandbox_runtime, run_id),
        )
        compatibility = _compatibility_response(
            request=request,
            native=native,
            approval=approval,
            default_collection=self.default_collection,
            system_prompt=self._system_prompt(),
            workspace_id=self.sandbox_runtime.workspaces.get_or_create(run_id).workspace_id,
        )
        durable_context = self._context_snapshot(snapshot, context)
        compatibility = compatibility.model_copy(
            update={
                "memory_snapshot": MemorySnapshot(
                    conversation_id=context.conversation_id,
                    window=0,
                    recent_turns=[],
                    total_turn_count=self.store.get_conversation(context.conversation_id).turn_count,
                    loaded_turn_count=0,
                    omitted_turn_count=0,
                    summary_text=durable_context.summary.summary_text,
                ),
                "memory_compaction": MemoryCompactionResult(
                    conversation_id=context.conversation_id,
                    attempted=durable_context.summary.triggered,
                    compacted=durable_context.summary.triggered,
                    summarized_turn_count=durable_context.summary.cutoff_index,
                    estimated_input_tokens=durable_context.estimated_message_tokens,
                    summary_text=durable_context.summary.summary_text,
                    reason=(
                        "DeepAgents SummarizationMiddleware 已生成 Context Summary。"
                        if durable_context.summary.triggered
                        else "当前 Context 未达到模型 Profile 的 Summary 阈值。"
                    ),
                ),
                "memory_write": MemoryWriteResult(
                    conversation_id=context.conversation_id,
                    turn_id=run_id,
                    saved=True,
                    reason="当前 messages 由 PostgreSQL Checkpointer 按稳定 thread_id 持久保存。",
                ),
                "context_bundle": compatibility.context_bundle.model_copy(
                    update={
                        "context_summary": (
                            "V3.17 的真实模型 Context 由 Checkpoint messages、DeepAgents Summary、"
                            "MemoryMiddleware profile、Tool schemas 与 System Prompt 动态组成；本字段仅为调试投影。"
                        )
                    }
                ),
            }
        )
        durable_native = DurableDeepAgentNativeResponse(
            **native.model_dump(mode="python"),
            thread_id=context.thread_id,
            durable_context=durable_context,
        )
        after_summary = self._summary_signature(graph, request, run_id)
        if after_summary != before_summary and durable_context.summary.triggered:
            self.store.add_audit(
                operation="summary",
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                assistant_id=context.assistant_id,
                conversation_id=context.conversation_id,
                run_id=run_id,
                actor="system",
                summary=f"Context Summary 覆盖到 message index {durable_context.summary.cutoff_index}。",
            )
            collector.emit_context_summary(durable_context)
        return DurableExecutionResult(
            status="waiting_for_approval" if waiting else "succeeded",
            compatibility_response=compatibility,
            native_response=durable_native,
            approval=approval,
        )

    def _context_snapshot(self, snapshot, context: DurableRuntimeContext) -> DurableContextSnapshot:
        messages: list[BaseMessage] = list(snapshot.values.get("messages", []))
        event = snapshot.values.get("_summarization_event") or {}
        summary_message = event.get("summary_message") if isinstance(event, dict) else None
        summary_text = _visible_content(getattr(summary_message, "content", "")) if summary_message else ""
        cutoff_index = int(event.get("cutoff_index", 0)) if isinstance(event, dict) else 0
        file_path = event.get("file_path") if isinstance(event, dict) else None
        return DurableContextSnapshot(
            conversation_id=context.conversation_id,
            thread_id=context.thread_id,
            run_id=context.run_id,
            thread_message_count=len(messages),
            estimated_message_tokens=count_tokens_approximately(messages) if messages else 0,
            model_context_tokens=self.model_context_tokens,
            summary_trigger_fraction=SUMMARY_TRIGGER_FRACTION,
            summary=ContextSummarySnapshot(
                triggered=bool(summary_text),
                cutoff_index=max(0, cutoff_index),
                summary_text=summary_text,
                history_file_path=str(file_path) if file_path else None,
            ),
            long_term_memories=self.memory_service.list(context),
            memory_profile_path=MEMORY_PROFILE_PATH,
            exact_wire_prompt_available=False,
        )

    def _runtime_context(self, request: DurableAgentAskRequest, run_id: str) -> DurableRuntimeContext:
        conversation = self.store.get_conversation(
            request.conversation_id or "",
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            assistant_id=request.assistant_id,
        )
        if conversation is None:
            raise KeyError(f"Conversation not found: {request.conversation_id}")
        return DurableRuntimeContext(
            tenant_id=conversation.tenant_id,
            user_id=conversation.user_id,
            assistant_id=conversation.assistant_id,
            conversation_id=conversation.conversation_id,
            thread_id=conversation.thread_id,
            run_id=run_id,
        )

    def _config(self, request: DurableAgentAskRequest, run_id: str) -> dict:
        context = self._runtime_context(request, run_id)
        return {
            "configurable": {"thread_id": context.thread_id},
            "recursion_limit": request.max_iterations,
        }

    def _system_prompt(self) -> str:
        catalog = "\n".join(
            f"- {item.collection}: {item.description}"
            for item in self.knowledge_bases
            if item.enabled
        )
        return f"{V317_SYSTEM_PROMPT}\n当前可选知识库：\n{catalog or '- 使用默认 Collection'}"

    def _approval_from_snapshot(self, snapshot, request, run_id):
        from obsidian_rag.v3_16.agent import DeepAgentService

        return DeepAgentService._approval_from_snapshot(self, snapshot, request, run_id)

    @staticmethod
    def _resume_decisions(steps, decision):
        output = []
        for step in steps:
            if decision.action == "allow":
                output.append({"type": "approve"})
            elif decision.action == "deny":
                output.append({"type": "reject", "message": decision.comment or "用户拒绝执行文件写入。"})
            else:
                arguments = decision.step_arguments.get(step.step_id, step.arguments)
                output.append({"type": "edit", "edited_action": {"name": step.tool_name, "args": arguments}})
        return output

    def _summary_signature(self, graph, request, run_id):
        snapshot = graph.get_state(self._config(request, run_id))
        event = snapshot.values.get("_summarization_event") or {}
        if not isinstance(event, dict):
            return None
        return (event.get("cutoff_index"), event.get("file_path"), _visible_content(getattr(event.get("summary_message"), "content", "")))


class _DurableExecutionCollector(_ExecutionCollector):
    def record_checkpoint_recovery(self, next_nodes) -> None:
        nodes = [str(node) for node in next_nodes]
        self._append_event(
            "checkpoint_recovery_started",
            status="running",
            detail="从稳定 Thread 的最近 PostgreSQL Checkpoint 继续执行。",
            node_name=nodes[0] if nodes else "checkpoint",
            metadata={"next_nodes": nodes},
        )
        self._emit(
            "progress",
            {"phase": "recovery", "status": "running", "next_nodes": nodes},
        )

    def emit_context_summary(self, context: DurableContextSnapshot) -> None:
        self._emit(
            "context_summary",
            {
                "conversation_id": context.conversation_id,
                "thread_id": context.thread_id,
                "cutoff_index": context.summary.cutoff_index,
                "history_file_path": context.summary.history_file_path,
                "estimated_message_tokens": context.estimated_message_tokens,
            },
        )


class _ReloadingMemoryMiddleware(MemoryMiddleware):
    """稳定 Thread 每次新 Run 都重读 profile，避免 Checkpoint 缓存旧 memory_contents。"""

    def before_agent(self, state, runtime, config):
        backend = self._get_backend(state, runtime, config)
        contents: dict[str, str] = {}
        results = backend.download_files(list(self.sources))
        for path, response in zip(self.sources, results, strict=True):
            if response.error is not None:
                if response.error == "file_not_found":
                    continue
                raise ValueError(f"Failed to download {path}: {response.error}")
            if response.content is not None:
                contents[path] = response.content.decode("utf-8")
        return MemoryStateUpdate(memory_contents=contents)


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
