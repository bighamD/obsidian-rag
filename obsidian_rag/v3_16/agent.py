from __future__ import annotations

import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from obsidian_rag.core.permissions import PermissionDecision, PermissionPrincipal, PermissionReport
from obsidian_rag.core.schemas import (
    AgentAskResponse,
    AgentNodeTiming,
    AgentTraceStep,
    AnswerStreamMetrics,
    ContextBundle,
    ContextChunk,
    EvidenceCheckResult,
    MemoryCompactionResult,
    MemorySnapshot,
    MemoryWriteResult,
    Plan,
    PlannerToolDefinition,
    PlanStep,
    StepResult,
    ToolObservation,
)
from obsidian_rag.v1.schemas import SearchHit
from obsidian_rag.v3_15.schemas import (
    ApprovalDecision as StoredApprovalDecision,
    ApprovalDecisionInput,
    ApprovalRequest,
    ApprovalStep,
)
from obsidian_rag.v3_16.artifacts import project_artifacts
from obsidian_rag.v3_16.backends import DeepAgentsSandboxBackend
from obsidian_rag.v3_16.schemas import (
    DeepAgentArtifact,
    DeepAgentAskRequest,
    DeepAgentExecutionEvent,
    DeepAgentExecutionResult,
    DeepAgentMessage,
    DeepAgentNativeResponse,
    DeepAgentToolCall,
    DeepAgentToolMessage,
)
from obsidian_rag.v3_16.tools import SearchNotesToolAdapter


SYSTEM_PROMPT = """你是 V3.16 DeepAgents 学习 Agent。你可以直接回答一般问题，也可以调用工具。

严格遵守以下业务规则：
1. 涉及本地知识库事实、菜谱、食品安全或用户要求“依据知识库”时，先调用 search_notes。
2. 如果用户要求把知识库内容生成文件，第一次模型响应只能调用 search_notes；必须等待真实 ToolMessage 后，下一次模型响应才能生成 write_file。
3. 不得在同一条 assistant 消息中并行调用 search_notes 和 write_file，也不得凭模型先验预制 write_file.content。
4. Markdown 正文必须依据 search_notes ToolMessage，保留关键步骤，并在“使用到的来源”章节列出 chunk_id 与 source。
5. 生成文件时写入 /artifacts/ 下有意义的英文短文件名，例如 /artifacts/mapo-tofu.md。只生成用户要求的一个最终文件。
6. write_file/edit_file 会触发人工审批。工具成功后，最终回答应说明文件已生成；不要再次写同一个文件。若用户拒绝审批，说明文件未生成并直接结束，不得再次请求文件写入。
7. 本版本禁止使用 execute 和 task；不运行 Shell，不委派 Sub-agent。简单任务不必调用 write_todos。
8. search_notes 没有证据时应明确说明，并且不要生成声称来自知识库的文件。
9. 只输出对用户可见的结论和工具事实，不输出隐藏推理或 chain-of-thought。
"""


class DeepAgentService:
    """将官方 create_deep_agent 映射到本仓库 Run、HITL、Sandbox 和 Console 契约。"""

    def __init__(
        self,
        *,
        model_factory,
        search_registry,
        knowledge_bases,
        sandbox_runtime,
        checkpointer,
        store,
        default_collection: str,
    ):
        self.model_factory = model_factory
        self.search_registry = search_registry
        self.knowledge_bases = list(knowledge_bases)
        self.sandbox_runtime = sandbox_runtime
        self.checkpointer = checkpointer
        self.store = store
        self.default_collection = default_collection

    def begin(self, request: DeepAgentAskRequest, run_id: str, event_sink=None) -> DeepAgentExecutionResult:
        graph = self._build_graph(request, run_id)
        collector = _ExecutionCollector(event_sink=event_sink)
        self._stream_graph(
            graph,
            {"messages": [{"role": "user", "content": request.question}]},
            request,
            run_id,
            collector,
        )
        return self._execution_result(graph, request, run_id, collector)

    def resume(
        self,
        run_id: str,
        decision: ApprovalDecisionInput,
        event_sink=None,
    ) -> DeepAgentExecutionResult:
        approval = self.store.get_approval(run_id)
        if approval is None:
            raise KeyError(f"Approval not found: {run_id}")
        if approval.status != "pending":
            raise ValueError(f"Approval already resolved: {run_id}")
        request = self.store.get_request(run_id)
        if request is None:
            raise KeyError(f"Deep Agent request not found: {run_id}")
        previous = self.store.get_response(run_id)
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
            decided_at=_now(),
        )
        self.store.resolve_approval(stored_decision)
        collector = _ExecutionCollector(
            event_sink=event_sink,
            previous=previous.deep_agent_response if previous else None,
        )
        collector.record_approval_resumed(decision.action)
        self._stream_graph(
            graph,
            Command(resume={"decisions": self._resume_decisions(approval.request.steps, decision)}),
            request,
            run_id,
            collector,
        )
        return self._execution_result(graph, request, run_id, collector)

    def checkpoint_ready(self, run_id: str = "deep_agent_health_probe") -> bool:
        try:
            graph = self._build_graph(DeepAgentAskRequest(question="health probe"), run_id)
            graph.get_state(self._config(DeepAgentAskRequest(question="health probe"), run_id))
        except Exception:
            return False
        return True

    def _build_graph(self, request: DeepAgentAskRequest, run_id: str):
        search_tool = SearchNotesToolAdapter(
            self.search_registry,
            request,
            self.knowledge_bases,
        ).as_tool()
        backend = DeepAgentsSandboxBackend(self.sandbox_runtime, run_id)
        return create_deep_agent(
            model=self.model_factory(),
            tools=[search_tool],
            system_prompt=self._system_prompt(),
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
            checkpointer=self.checkpointer,
            name="v3_16_deepagents_tool_loop",
        )

    def _system_prompt(self) -> str:
        catalog = "\n".join(
            f"- {item.collection}: {item.description}"
            for item in self.knowledge_bases
            if item.enabled
        )
        return f"{SYSTEM_PROMPT}\n当前可选知识库：\n{catalog or '- 使用默认 Collection'}"

    def _stream_graph(self, graph, input_value, request, run_id, collector) -> None:
        for event in graph.stream(
            input_value,
            self._config(request, run_id),
            stream_mode=["tasks", "updates", "messages"],
            version="v2",
            durability="sync",
        ):
            collector.consume(event)

    def _execution_result(self, graph, request, run_id, collector) -> DeepAgentExecutionResult:
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
        return DeepAgentExecutionResult(
            status="waiting_for_approval" if waiting else "succeeded",
            compatibility_response=compatibility,
            native_response=native,
            approval=approval,
        )

    def _approval_from_snapshot(self, snapshot, request, run_id):
        interrupt_item = snapshot.interrupts[0]
        payload = interrupt_item.value
        actions = list(payload.get("action_requests", []))
        last_ai = next(
            (message for message in reversed(snapshot.values.get("messages", [])) if isinstance(message, AIMessage)),
            None,
        )
        pending_calls = list(last_ai.tool_calls if last_ai else [])
        steps: list[ApprovalStep] = []
        permission_decisions: list[PermissionDecision] = []
        for index, action in enumerate(actions):
            tool_call = pending_calls[index] if index < len(pending_calls) else {}
            call_id = str(tool_call.get("id") or f"approval_step_{index + 1}")
            tool_name = str(action.get("name") or tool_call.get("name") or "unknown")
            arguments = dict(action.get("args") or tool_call.get("args") or {})
            reason = str(action.get("description") or "DeepAgents HumanInTheLoopMiddleware 要求人工确认。")
            steps.append(
                ApprovalStep(
                    step_id=call_id,
                    tool_name=tool_name,
                    reason=reason,
                    arguments=arguments,
                    risk_level="confirm",
                )
            )
            permission_decisions.append(
                PermissionDecision(
                    step_id=call_id,
                    kind="tool",
                    tool_name=tool_name,
                    source="deepagents",
                    risk_level="confirm",
                    decision="confirm",
                    reason=reason,
                    required_permissions=["sandbox.write"],
                    argument_names=sorted(arguments),
                )
            )
        report = PermissionReport(
            principal=PermissionPrincipal(
                subject_id="deepagents_v3_16",
                roles=["user"],
                permissions=["knowledge.read", "sandbox.read", "sandbox.write"],
                tool_allowlist=["search_notes", "write_file", "edit_file", "read_file", "ls", "glob", "grep"],
                allowed_collections=["*"],
            ),
            decisions=permission_decisions,
            allow_count=0,
            confirm_count=len(permission_decisions),
            deny_count=0,
            all_allowed=False,
            summary=f"DeepAgents interrupt_on 捕获 {len(permission_decisions)} 个写入 Tool Call。",
        )
        existing = self.store.get_approval(run_id)
        if existing is not None:
            if existing.status == "pending":
                return existing
            raise RuntimeError("V3.16 每个 Run 只支持一个写入审批轮次；模型不应在已决审批后再次请求写入。")
        return self.store.save_pending_approval(
            ApprovalRequest(
                approval_id=f"approval_{interrupt_item.id[:16]}",
                run_id=run_id,
                conversation_id=request.conversation_id or run_id,
                summary="Deep Agent 已读取前序 ToolMessage，准备写入 Artifact。",
                steps=steps,
                permission_report=report,
                created_at=_now(),
            )
        )

    def _resume_decisions(self, steps: list[ApprovalStep], decision: ApprovalDecisionInput) -> list[dict[str, Any]]:
        output = []
        for step in steps:
            if decision.action == "allow":
                output.append({"type": "approve"})
            elif decision.action == "deny":
                output.append({"type": "reject", "message": decision.comment or "用户拒绝执行文件写入。"})
            else:
                arguments = decision.step_arguments.get(step.step_id, step.arguments)
                output.append(
                    {
                        "type": "edit",
                        "edited_action": {"name": step.tool_name, "args": arguments},
                    }
                )
        return output

    @staticmethod
    def _config(request: DeepAgentAskRequest, run_id: str) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": run_id},
            "recursion_limit": request.max_iterations,
        }


class _ExecutionCollector:
    """消费 LangGraph v2 tasks/updates stream，提取公开执行事实。"""

    def __init__(self, *, event_sink=None, previous: DeepAgentNativeResponse | None = None):
        self.event_sink = event_sink
        self.events = list(previous.execution_events) if previous else []
        self.graph_path = list(previous.graph_path) if previous else []
        self.node_timings = list(previous.node_timings) if previous else []
        self._task_starts: dict[str, tuple[str, float, str]] = {}
        self._answer_sequence = 0

    def consume(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        data = event.get("data") or {}
        if event_type == "tasks":
            self._consume_task(data)
        elif event_type == "updates":
            self._consume_update(data)

    def record_approval_resumed(self, action: str) -> None:
        self._append_event(
            "approval_resumed",
            status="completed",
            detail=f"收到人工决定 {action}，使用 Command(resume=...) 恢复 Graph。",
            node_name="HumanInTheLoopMiddleware.after_model",
            metadata={"action": action},
        )
        self._emit("progress", {"phase": "approval", "status": "completed", "action": action})

    def _consume_task(self, data: dict[str, Any]) -> None:
        task_id = str(data.get("id") or "")
        node_name = str(data.get("name") or "unknown")
        is_finished = "result" in data or "error" in data
        if not is_finished:
            started_at = _now()
            self._task_starts[task_id] = (node_name, perf_counter(), started_at)
            self.graph_path.append(node_name)
            self._append_event(
                "node_started",
                status="running",
                detail=f"DeepAgents 节点 {node_name} 开始执行。",
                node_name=node_name,
            )
            if node_name == "model":
                phase = "planning" if not any(item.event_type == "model_completed" for item in self.events) else "answer"
                self._emit("progress", {"phase": phase, "status": "running"})
            if node_name == "tools":
                for call in data.get("input") or []:
                    if not isinstance(call, dict):
                        continue
                    self._emit(
                        "tool_started",
                        {
                            "step_id": call.get("id") or call.get("name"),
                            "tool_name": call.get("name"),
                            "source": "deepagents",
                            "status": "running",
                        },
                    )
                    if call.get("name") == "search_notes":
                        self._emit("progress", {"phase": "retrieval", "status": "running"})
            return

        start = self._task_starts.pop(task_id, None)
        duration_ms = max(0, round((perf_counter() - start[1]) * 1000)) if start else 0
        started_at = start[2] if start else _now()
        finished_at = _now()
        self.node_timings.append(
            AgentNodeTiming(
                node_name=node_name,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
            )
        )
        error = data.get("error")
        self._append_event(
            "node_finished",
            status="failed" if error else "completed",
            detail=f"DeepAgents 节点 {node_name} {'执行失败' if error else '执行完成'}。",
            node_name=node_name,
            duration_ms=duration_ms,
            metadata={"error": str(error)} if error else {},
        )
        self._emit(
            "node_finished",
            {"node_name": node_name, "duration_ms": duration_ms, "status": "failed" if error else "completed"},
        )

    def _consume_update(self, data: dict[str, Any]) -> None:
        if "model" in data:
            for message in (data.get("model") or {}).get("messages", []):
                if not isinstance(message, AIMessage):
                    continue
                if message.tool_calls:
                    self._append_event(
                        "model_completed",
                        status="completed",
                        detail=f"模型生成 {len(message.tool_calls)} 个 Tool Call。",
                        node_name="model",
                        metadata={"tool_names": [call.get("name") for call in message.tool_calls]},
                    )
                    for call in message.tool_calls:
                        self._append_event(
                            "tool_requested",
                            status="requested",
                            detail=f"模型请求工具 {call.get('name', 'unknown')}。",
                            node_name="model",
                            tool_name=str(call.get("name") or "unknown"),
                            tool_call_id=str(call.get("id") or ""),
                            metadata={"argument_names": sorted((call.get("args") or {}).keys())},
                        )
                else:
                    content = _visible_content(message.content)
                    self._append_event(
                        "answer_completed",
                        status="completed",
                        detail="模型生成最终可见回答。",
                        node_name="model",
                    )
                    self._emit("progress", {"phase": "answer", "status": "completed"})
                    if content:
                        self._answer_sequence += 1
                        self._emit(
                            "answer_delta",
                            {
                                "message_id": message.id or f"answer_{uuid4().hex[:12]}",
                                "sequence": self._answer_sequence,
                                "delta": content,
                            },
                        )

        if "tools" in data:
            for message in (data.get("tools") or {}).get("messages", []):
                if not isinstance(message, ToolMessage):
                    continue
                parsed = _parse_content(message.content)
                failed = getattr(message, "status", None) == "error" or (
                    isinstance(parsed, dict) and parsed.get("status") == "failed"
                )
                result_count = int(parsed.get("result_count", 0)) if isinstance(parsed, dict) else 0
                self._append_event(
                    "tool_completed",
                    status="failed" if failed else "completed",
                    detail=f"工具 {message.name or 'unknown'} 返回 Observation。",
                    node_name="tools",
                    tool_name=message.name,
                    tool_call_id=message.tool_call_id,
                    metadata={"result_count": result_count},
                )
                self._emit(
                    "tool_finished",
                    {
                        "step_id": message.tool_call_id,
                        "tool_name": message.name or "unknown",
                        "source": "deepagents",
                        "status": "failed" if failed else "success",
                        "result_count": result_count,
                    },
                )
                if message.name == "search_notes":
                    self._emit(
                        "progress",
                        {"phase": "retrieval", "status": "completed", "result_count": result_count},
                    )

        if "__interrupt__" in data:
            interrupts = data.get("__interrupt__") or []
            tool_names = []
            for item in interrupts:
                value = getattr(item, "value", {})
                tool_names.extend(action.get("name") for action in value.get("action_requests", []))
            self._append_event(
                "approval_requested",
                status="waiting",
                detail=f"HumanInTheLoopMiddleware 暂停 {len(tool_names)} 个写入 Tool Call。",
                node_name="HumanInTheLoopMiddleware.after_model",
                metadata={"tool_names": tool_names},
            )
            self._emit("progress", {"phase": "approval", "status": "running", "tool_names": tool_names})

    def _append_event(
        self,
        event_type,
        *,
        status: str,
        detail: str,
        node_name: str | None = None,
        duration_ms: int | None = None,
        tool_name: str | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            DeepAgentExecutionEvent(
                sequence=len(self.events) + 1,
                event_type=event_type,
                node_name=node_name,
                status=status,
                detail=detail,
                occurred_at=_now(),
                duration_ms=duration_ms,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                metadata=metadata or {},
            )
        )

    def _emit(self, name: str, payload: dict[str, Any]) -> None:
        if self.event_sink is not None:
            self.event_sink(name, payload)


def _native_response(
    *,
    run_id: str,
    request: DeepAgentAskRequest,
    messages: list[BaseMessage],
    waiting: bool,
    collector: _ExecutionCollector,
    artifacts: list[DeepAgentArtifact],
) -> DeepAgentNativeResponse:
    waiting_ids = _waiting_tool_call_ids(messages) if waiting else set()
    tool_message_by_call: dict[str, ToolMessage] = {
        message.tool_call_id: message
        for message in messages
        if isinstance(message, ToolMessage)
    }
    model_call_index = 0
    call_sequence = 0
    projected_messages: list[DeepAgentMessage] = []
    projected_calls: list[DeepAgentToolCall] = []
    projected_tool_messages: list[DeepAgentToolMessage] = []
    search_results: list[SearchHit] = []
    selected_collections: list[str] = []

    for message_index, message in enumerate(messages, start=1):
        role = _message_role(message)
        message_calls: list[DeepAgentToolCall] = []
        if isinstance(message, AIMessage):
            model_call_index += 1
            for call in message.tool_calls:
                call_sequence += 1
                call_id = str(call.get("id") or f"tool_call_{call_sequence}")
                status = _tool_call_status(call_id, tool_message_by_call.get(call_id), waiting_ids)
                projected = DeepAgentToolCall(
                    sequence=call_sequence,
                    model_call_index=model_call_index,
                    call_id=call_id,
                    name=str(call.get("name") or "unknown"),
                    arguments=dict(call.get("args") or {}),
                    status=status,
                )
                message_calls.append(projected)
                projected_calls.append(projected)
        projected_messages.append(
            DeepAgentMessage(
                sequence=message_index,
                message_id=getattr(message, "id", None),
                role=role,
                content=_parse_content(message.content) if isinstance(message, ToolMessage) else message.content,
                tool_calls=message_calls,
                tool_call_id=getattr(message, "tool_call_id", None),
                tool_name=getattr(message, "name", None),
            )
        )
        if isinstance(message, ToolMessage):
            parsed = _parse_content(message.content)
            tool_status = _tool_message_status(message, parsed)
            tool_name = message.name or _tool_name_for_call(projected_calls, message.tool_call_id)
            projected_tool_messages.append(
                DeepAgentToolMessage(
                    sequence=message_index,
                    message_id=message.id,
                    tool_call_id=message.tool_call_id,
                    tool_name=tool_name or "unknown",
                    status=tool_status,
                    content=parsed,
                    summary=_tool_message_summary(tool_name, parsed, tool_status),
                )
            )
            if tool_name == "search_notes" and isinstance(parsed, dict):
                selected_collections.extend(str(item) for item in parsed.get("selected_collections", []))
                for item in parsed.get("results", []):
                    try:
                        search_results.append(SearchHit.model_validate(item))
                    except Exception:
                        continue

    final_answer = next(
        (
            _visible_content(message.content)
            for message in reversed(messages)
            if isinstance(message, AIMessage) and not message.tool_calls and _visible_content(message.content)
        ),
        "",
    )
    if waiting and not final_answer:
        final_answer = "已读取知识库 Observation 并准备生成文件，当前等待人工审批。"
    return DeepAgentNativeResponse(
        run_id=run_id,
        status="waiting_for_approval" if waiting else "succeeded",
        question=request.question,
        model_call_count=model_call_index,
        messages=projected_messages,
        tool_calls=projected_calls,
        tool_messages=projected_tool_messages,
        execution_events=collector.events,
        graph_path=collector.graph_path,
        node_timings=collector.node_timings,
        final_answer=final_answer or "Deep Agent 已结束，但没有生成可见回答。",
        selected_collections=_stable_unique(selected_collections),
        search_results=_dedupe_hits(search_results),
        artifacts=artifacts,
    )


def _compatibility_response(
    *,
    request: DeepAgentAskRequest,
    native: DeepAgentNativeResponse,
    approval,
    default_collection: str,
    system_prompt: str,
    workspace_id: str,
) -> AgentAskResponse:
    tool_messages = {item.tool_call_id: item for item in native.tool_messages}
    plan_steps: list[PlanStep] = []
    step_results: list[StepResult] = []
    observations: list[ToolObservation] = []
    previous_step_id: str | None = None
    search_step_ids: list[str] = []

    for call in native.tool_calls:
        kind = "search" if call.name == "search_notes" else "tool"
        step = PlanStep(
            id=call.call_id,
            kind=kind,
            query=str(call.arguments.get("query")) if kind == "search" and call.arguments.get("query") else None,
            tool_name=None if kind == "search" else call.name,
            arguments=call.arguments,
            depends_on=[previous_step_id] if previous_step_id else [],
            reason=f"第 {call.model_call_index} 次模型调用基于当前 messages 动态选择 {call.name}。",
        )
        plan_steps.append(step)
        previous_step_id = call.call_id
        tool_message = tool_messages.get(call.call_id)
        if kind == "search":
            search_step_ids.append(call.call_id)
            hits = _search_hits_from_tool_message(tool_message)
            step_results.append(
                StepResult(
                    step_id=call.call_id,
                    kind="search",
                    tool_name="search_notes",
                    query=step.query,
                    arguments=call.arguments,
                    status=_step_status(call.status),
                    result_count=len(hits),
                    results=hits,
                    sources=_sources(hits),
                    reason=step.reason,
                    error=tool_message.summary if tool_message and tool_message.status == "failed" else None,
                )
            )
        else:
            observation = ToolObservation(
                step_id=call.call_id,
                tool_name=call.name,
                source="deepagents",
                status=_step_status(call.status),
                data=tool_message.content if tool_message else {"arguments": call.arguments},
                summary=tool_message.summary if tool_message else f"{call.name} 尚未执行。",
                metadata={"model_call_index": call.model_call_index},
                error=tool_message.summary if tool_message and tool_message.status in {"failed", "rejected"} else None,
            )
            observations.append(observation)
            step_results.append(
                StepResult(
                    step_id=call.call_id,
                    kind="tool",
                    tool_name=call.name,
                    arguments=call.arguments,
                    status=_step_status(call.status),
                    reason=step.reason,
                    observation=observation,
                    error=observation.error,
                )
            )

    if not plan_steps:
        plan_steps.append(
            PlanStep(
                id="direct_answer",
                kind="synthesize",
                instruction="Deep Agent 未调用工具，直接生成回答。",
                reason="模型判断当前问题不需要外部 Observation。",
            )
        )

    included_chunks = [
        ContextChunk(
            step_id=search_step_ids[0] if search_step_ids else None,
            **hit.model_dump(mode="python"),
            reason="该 chunk 来自 search_notes ToolMessage，并进入后续模型调用的 messages。",
        )
        for hit in native.search_results
    ]
    context_messages = [{"role": "system", "content": system_prompt}]
    context_messages.extend(
        {
            "role": message.role,
            "content": _json_text(message.content),
        }
        for message in native.messages
    )
    evidence_ok = not search_step_ids or bool(native.search_results)
    traces = _compatibility_trace(native)
    conversation_id = request.conversation_id or f"conv_{native.run_id}"
    artifacts = [item.model_copy(update={}) for item in native.artifacts]
    model_generation_ms = sum(
        timing.duration_ms for timing in native.node_timings if timing.node_name == "model"
    )
    return AgentAskResponse(
        run_id=native.run_id,
        conversation_id=conversation_id,
        question=request.question,
        collection=(native.selected_collections[0] if native.selected_collections else request.collection or default_collection),
        answer=native.final_answer,
        used_retrieval=bool(search_step_ids),
        sources=_sources(native.search_results),
        plan=Plan(goal=request.question, steps=plan_steps),
        tool_catalog=[
            PlannerToolDefinition(
                name="search_notes",
                description="本地知识库检索，结果作为 ToolMessage 返回。",
                input_schema={"type": "object", "required": ["query"]},
                source="local",
                read_only=True,
            ),
            PlannerToolDefinition(
                name="write_file",
                description="把基于前序 Observation 生成的内容写入 /artifacts/。",
                input_schema={"type": "object", "required": ["file_path", "content"]},
                source="deepagents-backend",
                read_only=False,
            ),
        ],
        permission_report=approval.request.permission_report if approval else None,
        sandbox_workspace_id=workspace_id,
        sandbox_artifacts=[item for item in artifacts],
        step_results=step_results,
        retry_step_results=[],
        evidence_check=EvidenceCheckResult(
            is_sufficient=evidence_ok,
            missing_points=[] if evidence_ok else ["search_notes 没有返回知识库证据。"],
            checked_step_ids=search_step_ids,
            missing_step_ids=[] if evidence_ok else search_step_ids,
            reason=(
                "search_notes ToolMessage 已提供后续模型调用需要的证据。"
                if evidence_ok and search_step_ids
                else "当前问题没有调用知识库检索。"
                if not search_step_ids
                else "search_notes ToolMessage 没有返回有效 chunks。"
            ),
        ),
        context_bundle=ContextBundle(
            messages=context_messages,
            included_chunks=included_chunks,
            excluded_chunks=[],
            tool_observations=observations,
            token_budget=0,
            context_summary=(
                "V3.16 不再单独构建一次性 Answer Context；DeepAgents 将 HumanMessage、AIMessage 和 ToolMessage 持续保存在 messages。"
            ),
        ),
        memory_snapshot=MemorySnapshot(
            conversation_id=conversation_id,
            window=0,
            recent_turns=[],
            total_turn_count=0,
            loaded_turn_count=0,
            omitted_turn_count=0,
            summary_text="",
        ),
        memory_compaction=MemoryCompactionResult(
            conversation_id=conversation_id,
            attempted=False,
            compacted=False,
            reason="V3.16 Checkpointer 只服务当前 Run 的 Tool Loop/HITL；多轮 Memory 和摘要进入 V3.17。",
        ),
        memory_write=MemoryWriteResult(
            conversation_id=conversation_id,
            saved=False,
            reason="V3.16 不写入 Conversation Memory；持久多轮对话进入 V3.17。",
        ),
        graph_path=native.graph_path,
        trace=traces,
        node_timings=native.node_timings,
        answer_stream=AnswerStreamMetrics(
            mode="stream",
            llm_generation_ms=model_generation_ms,
            visible_character_count=len(native.final_answer),
        ),
    )


def _compatibility_trace(native: DeepAgentNativeResponse) -> list[AgentTraceStep]:
    traces = []
    for event in native.execution_events:
        if event.event_type == "model_completed":
            step_type = "planner"
        elif event.event_type == "tool_completed":
            step_type = "tool_result"
        elif event.event_type in {"approval_requested", "approval_resumed"}:
            step_type = "approval"
        elif event.event_type == "answer_completed":
            step_type = "synthesize"
        else:
            continue
        traces.append(
            AgentTraceStep(
                node_name=event.node_name or event.event_type,
                step_type=step_type,
                step_id=event.tool_call_id,
                tool_name=event.tool_name,
                result_count=event.metadata.get("result_count"),
                reason=event.detail,
                metadata=event.metadata,
            )
        )
    return traces


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, ToolMessage):
        return "tool"
    if message.type == "system":
        return "system"
    return "other"


def _waiting_tool_call_ids(messages: list[BaseMessage]) -> set[str]:
    last_ai = next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)
    return {str(call.get("id")) for call in (last_ai.tool_calls if last_ai else []) if call.get("id")}


def _tool_call_status(call_id: str, message: ToolMessage | None, waiting_ids: set[str]):
    if call_id in waiting_ids and message is None:
        return "waiting_for_approval"
    if message is None:
        return "requested"
    parsed = _parse_content(message.content)
    status = _tool_message_status(message, parsed)
    return "rejected" if status == "rejected" else "failed" if status == "failed" else "success"


def _tool_message_status(message: ToolMessage, parsed: Any) -> str:
    if getattr(message, "status", None) == "error":
        content = _visible_content(message.content).lower()
        return "rejected" if "reject" in content or "拒绝" in content else "failed"
    if isinstance(parsed, dict) and parsed.get("status") == "failed":
        return "failed"
    return "success"


def _tool_message_summary(tool_name: str | None, content: Any, status: str) -> str:
    if tool_name == "search_notes" and isinstance(content, dict):
        return (
            f"search_notes 返回 {content.get('result_count', 0)} 条结果；"
            f"Collections: {', '.join(content.get('selected_collections', [])) or '-'}。"
        )
    text = _visible_content(content).strip()
    return text[:240] if text else f"{tool_name or 'Tool'} {status}。"


def _tool_name_for_call(calls: list[DeepAgentToolCall], call_id: str) -> str | None:
    return next((call.name for call in calls if call.call_id == call_id), None)


def _search_hits_from_tool_message(message: DeepAgentToolMessage | None) -> list[SearchHit]:
    if message is None or not isinstance(message.content, dict):
        return []
    output = []
    for item in message.content.get("results", []):
        try:
            output.append(SearchHit.model_validate(item))
        except Exception:
            continue
    return output


def _step_status(status: str) -> str:
    if status == "success":
        return "success"
    if status in {"failed", "rejected"}:
        return "failed"
    return "skipped"


def _sources(hits: list[SearchHit]) -> list[str]:
    return _stable_unique(
        f"{hit.chunk_id}: {hit.source}" if hit.chunk_id else hit.source
        for hit in hits
    )


def _dedupe_hits(hits: list[SearchHit]) -> list[SearchHit]:
    seen = set()
    output = []
    for hit in hits:
        key = (hit.chunk_id, hit.source, hit.text or hit.text_preview)
        if key in seen:
            continue
        seen.add(key)
        output.append(hit)
    return output


def _stable_unique(values) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _parse_content(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    stripped = content.strip()
    if not stripped or stripped[0] not in "[{":
        return content
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return content


def _visible_content(content: Any) -> str:
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
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content or "")


def _json_text(content: Any) -> str:
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
