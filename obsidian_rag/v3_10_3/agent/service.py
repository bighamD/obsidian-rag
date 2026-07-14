from __future__ import annotations

import operator
import uuid
from threading import RLock
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, Send

from obsidian_rag.prompting import format_sources
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3_4.planner.service import PlannerService
from obsidian_rag.v3_4.schemas import Plan, PlanRequest, PlanStep
from obsidian_rag.v3_8_1.compaction import ConversationCompactor
from obsidian_rag.v3_8_1.context import ContextBuilder, build_memory_aware_planner_question
from obsidian_rag.v3_8_1.schemas import (
    ContextBundle,
    EvidenceCheckResult,
    MemoryCompactionResult,
    MemorySnapshot,
    MemoryWriteResult,
    StepResult,
)
from obsidian_rag.v3_10_3.schemas import (
    AdvancedAskRequest,
    AdvancedAskResponse,
    AdvancedTraceStep,
    RouteDecision,
    SearchTask,
    StateHistoryEntry,
    StateHistoryResponse,
)


STREAM_MODES = ["updates", "messages", "custom"]
CHECKPOINT_TYPES = [
    AdvancedAskRequest,
    AdvancedTraceStep,
    RouteDecision,
    SearchTask,
    Plan,
    PlanRequest,
    PlanStep,
    StepResult,
    EvidenceCheckResult,
    ContextBundle,
    MemorySnapshot,
    MemoryCompactionResult,
    MemoryWriteResult,
]


class TransientSearchError(RuntimeError):
    """仅用于演示 RetryPolicy 的可重试检索异常。"""


def _merge_dicts(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {**left, **right}


class PlannerSubgraphState(TypedDict, total=False):
    request: AdvancedAskRequest
    memory_snapshot: MemorySnapshot
    planner_request: PlanRequest
    plan: Plan
    search_tasks: list[SearchTask]
    planner_subgraph_path: Annotated[list[str], operator.add]
    planner_trace: Annotated[list[AdvancedTraceStep], operator.add]


class AdvancedAgentState(TypedDict, total=False):
    request: AdvancedAskRequest
    run_id: str
    thread_id: str
    conversation_id: str
    memory_snapshot: MemorySnapshot
    memory_compaction: MemoryCompactionResult
    plan: Plan
    search_tasks: list[SearchTask]
    active_task: SearchTask
    planner_subgraph_path: Annotated[list[str], operator.add]
    planner_trace: Annotated[list[AdvancedTraceStep], operator.add]
    step_results: Annotated[list[StepResult], operator.add]
    retry_step_results: Annotated[list[StepResult], operator.add]
    evidence_check: EvidenceCheckResult
    context_bundle: ContextBundle
    answer: str
    used_retrieval: bool
    sources: list[str]
    business_retry_count: int
    graph_path: Annotated[list[str], operator.add]
    trace: Annotated[list[AdvancedTraceStep], operator.add]
    route_decisions: Annotated[list[RouteDecision], operator.add]
    node_retry_counts: Annotated[dict[str, int], _merge_dicts]
    memory_write: MemoryWriteResult


class AdvancedAgentService:
    """演示 Subgraph、Send、Command、RetryPolicy、History 和 messages stream。"""

    def __init__(
        self,
        retrieval_service,
        planner_service: PlannerService,
        chat_model,
        memory_store,
        memory_compactor: ConversationCompactor | None = None,
        checkpointer: InMemorySaver | None = None,
        context_builder: ContextBuilder | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.planner_service = planner_service
        self.chat_model = chat_model
        self.memory_store = memory_store
        self.memory_compactor = memory_compactor
        self.checkpointer = checkpointer or InMemorySaver(
            serde=JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_TYPES)
        )
        self.context_builder = context_builder
        self._attempts: dict[str, int] = {}
        self._attempt_lock = RLock()
        self.graph = self._build_graph()

    def ask(self, request: AdvancedAskRequest, run_id: str | None = None) -> AdvancedAskResponse:
        run_id = run_id or f"adv_{uuid.uuid4().hex[:12]}"
        thread_id = request.thread_id or f"thread_{uuid.uuid4().hex[:12]}"
        config = self._config(thread_id)
        try:
            final_state = self.graph.invoke(self._initial_state(request, run_id, thread_id), config=config)
            return self._response_from_state(final_state, request, run_id, thread_id)
        finally:
            self._clear_attempts(run_id)

    def stream_events(self, request: AdvancedAskRequest, run_id: str):
        thread_id = request.thread_id or f"thread_{uuid.uuid4().hex[:12]}"
        config = self._config(thread_id)
        try:
            for item in self.graph.stream(
                self._initial_state(request, run_id, thread_id),
                config=config,
                stream_mode=STREAM_MODES,
                subgraphs=True,
                version="v2",
            ):
                normalized = _normalize_stream_item(item)
                if normalized is not None:
                    yield normalized

            snapshot = self.graph.get_state(config)
            response = self._response_from_state(snapshot.values, request, run_id, thread_id)
        finally:
            self._clear_attempts(run_id)
        yield {
            "name": "final_response",
            "detail": "Advanced Graph 已完成，并生成最终 JSON 响应。",
            "data": {"response": response.model_dump(mode="json")},
        }

    def get_history(self, thread_id: str, limit: int = 20) -> StateHistoryResponse:
        config = self._config(thread_id)
        entries = []
        for snapshot in self.graph.get_state_history(config, limit=limit):
            values = snapshot.values or {}
            checkpoint_id = (snapshot.config.get("configurable") or {}).get("checkpoint_id")
            entries.append(
                StateHistoryEntry(
                    checkpoint_id=checkpoint_id,
                    created_at=snapshot.created_at,
                    next_nodes=list(snapshot.next),
                    state_keys=sorted(values.keys()),
                    graph_path=list(values.get("graph_path", [])),
                    step_result_count=len(values.get("step_results", [])),
                    retry_result_count=len(values.get("retry_step_results", [])),
                    answer_preview=str(values.get("answer", ""))[:160],
                )
            )
        return StateHistoryResponse(thread_id=thread_id, entries=entries)

    def _build_graph(self):
        graph = StateGraph(AdvancedAgentState)
        planner_subgraph = self._build_planner_subgraph()
        retry_policy = RetryPolicy(
            initial_interval=0.05,
            backoff_factor=2.0,
            max_interval=0.2,
            max_attempts=2,
            jitter=False,
            retry_on=TransientSearchError,
        )

        graph.add_node("load_memory", self._load_memory_node)
        graph.add_node("compact_memory", self._compact_memory_node)
        graph.add_node("planner_subgraph", planner_subgraph)
        graph.add_node("route_plan", self._route_plan_node, destinations=("dispatch_search", "build_context"))
        graph.add_node("dispatch_search", self._dispatch_search_node)
        graph.add_node("search_worker", self._search_worker_node, retry_policy=retry_policy)
        graph.add_node("evidence_check", self._evidence_check_node)
        graph.add_node("route_evidence", self._route_evidence_node, destinations=("dispatch_retry", "build_context"))
        graph.add_node("dispatch_retry", self._dispatch_retry_node)
        graph.add_node("retry_search_worker", self._retry_search_worker_node, retry_policy=retry_policy)
        graph.add_node("build_context", self._build_context_node)
        graph.add_node("answer", self._answer_node)
        graph.add_node("save_memory", self._save_memory_node)

        graph.add_edge(START, "load_memory")
        graph.add_edge("load_memory", "compact_memory")
        graph.add_edge("compact_memory", "planner_subgraph")
        graph.add_edge("planner_subgraph", "route_plan")
        graph.add_conditional_edges("dispatch_search", self._send_initial_tasks)
        graph.add_edge("search_worker", "evidence_check")
        graph.add_edge("evidence_check", "route_evidence")
        graph.add_conditional_edges("dispatch_retry", self._send_retry_tasks)
        graph.add_edge("retry_search_worker", "evidence_check")
        graph.add_edge("build_context", "answer")
        graph.add_edge("answer", "save_memory")
        graph.add_edge("save_memory", END)
        return graph.compile(checkpointer=self.checkpointer, name="v3_10_3_advanced_graph")

    def _build_planner_subgraph(self):
        graph = StateGraph(PlannerSubgraphState)
        graph.add_node("prepare_planner_input", self._prepare_planner_input_node)
        graph.add_node("call_planner", self._call_planner_node)
        graph.add_edge(START, "prepare_planner_input")
        graph.add_edge("prepare_planner_input", "call_planner")
        graph.add_edge("call_planner", END)
        return graph.compile(name="planner_subgraph")

    def _load_memory_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        request = state["request"]
        snapshot = self.memory_store.load_snapshot(state["conversation_id"], window=request.memory_window)
        return {
            "memory_snapshot": snapshot,
            "graph_path": ["load_memory"],
            "trace": [
                AdvancedTraceStep(
                    node_name="load_memory",
                    kind="memory",
                    detail=f"读取最近 {snapshot.loaded_turn_count} 个原始 Turn。",
                    metadata={"total_turn_count": snapshot.total_turn_count},
                )
            ],
        }

    def _compact_memory_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        request = state["request"]
        if not request.memory_compaction_enabled or self.memory_compactor is None:
            result = MemoryCompactionResult(
                conversation_id=state["conversation_id"],
                reason="本次请求关闭 Compaction，或没有配置 ConversationCompactor。",
            )
            snapshot = state["memory_snapshot"]
        else:
            result = self.memory_compactor.compact(
                conversation_id=state["conversation_id"],
                keep_recent_turns=request.memory_window,
                trigger_turns=request.memory_compaction_trigger_turns,
                trigger_tokens=request.memory_compaction_trigger_tokens,
            )
            snapshot = (
                self.memory_store.load_snapshot(state["conversation_id"], window=request.memory_window)
                if result.compacted
                else state["memory_snapshot"]
            )
        return {
            "memory_compaction": result,
            "memory_snapshot": snapshot,
            "graph_path": ["compact_memory"],
            "trace": [
                AdvancedTraceStep(
                    node_name="compact_memory",
                    kind="memory",
                    detail=result.reason,
                    metadata={"compacted": result.compacted, "attempted": result.attempted},
                )
            ],
        }

    def _prepare_planner_input_node(self, state: PlannerSubgraphState) -> dict[str, Any]:
        request = state["request"]
        question = build_memory_aware_planner_question(request.question, state["memory_snapshot"])
        planner_request = PlanRequest(
            question=question,
            top_k=request.top_k,
            mode=request.mode,
            filters=request.filters,
            max_steps=request.max_steps,
        )
        return {
            "planner_request": planner_request,
            "planner_subgraph_path": ["prepare_planner_input"],
            "planner_trace": [
                AdvancedTraceStep(
                    node_name="prepare_planner_input",
                    kind="subgraph",
                    detail="Planner 子图已组装当前问题、滚动摘要和最近原始 Turns。",
                )
            ],
        }

    def _call_planner_node(self, state: PlannerSubgraphState) -> dict[str, Any]:
        response = self.planner_service.plan(state["planner_request"])
        request = state["request"]
        tasks = [
            SearchTask(step_id=step.id, query=step.query or request.question, reason=step.reason)
            for step in response.plan.steps
            if step.kind == "search"
        ][: request.max_parallel_searches]
        return {
            "plan": response.plan,
            "search_tasks": tasks,
            "planner_subgraph_path": ["call_planner", *response.graph_path],
            "planner_trace": [
                AdvancedTraceStep(
                    node_name="call_planner",
                    kind="subgraph",
                    detail=f"Planner 子图生成 {len(response.plan.steps)} 个步骤，其中 {len(tasks)} 个可并行 search task。",
                    metadata={"task_ids": [task.step_id for task in tasks]},
                )
            ],
        }

    def _route_plan_node(self, state: AdvancedAgentState) -> Command:
        has_search = bool(state.get("search_tasks"))
        destination = "dispatch_search" if has_search else "build_context"
        reason = "计划包含 search step，进入 Send 并行分发。" if has_search else "计划不包含 search step，跳过检索。"
        return Command(
            goto=destination,
            update={
                "graph_path": ["route_plan"],
                "route_decisions": [RouteDecision(node_name="route_plan", destination=destination, reason=reason)],
                "trace": [AdvancedTraceStep(node_name="route_plan", kind="command", detail=reason)],
            },
        )

    def _dispatch_search_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        tasks = state.get("search_tasks", [])
        return {
            "graph_path": ["dispatch_search"],
            "trace": [
                AdvancedTraceStep(
                    node_name="dispatch_search",
                    kind="send",
                    detail=f"即将通过 Send 并行分发 {len(tasks)} 个检索任务。",
                    metadata={"task_ids": [task.step_id for task in tasks]},
                )
            ],
        }

    def _send_initial_tasks(self, state: AdvancedAgentState) -> list[Send]:
        return [
            Send(
                "search_worker",
                {
                    "request": state["request"],
                    "run_id": state["run_id"],
                    "thread_id": state["thread_id"],
                    "active_task": task,
                },
            )
            for task in state.get("search_tasks", [])
        ]

    def _search_worker_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        request = state["request"]
        task = state["active_task"]
        attempt_key = f"{state['run_id']}:{task.step_id}:initial"
        attempt = self._next_attempt(attempt_key)
        if request.simulate_transient_search_failure and attempt == 1:
            get_stream_writer()(
                {
                    "kind": "retry_policy",
                    "node_name": "search_worker",
                    "task_id": task.step_id,
                    "attempt": attempt,
                    "detail": "教学开关触发临时异常，LangGraph RetryPolicy 将自动重新执行节点。",
                }
            )
            raise TransientSearchError(f"模拟临时检索失败：{task.step_id}")

        results = list(
            self.retrieval_service.search(
                task.query,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
            )
        )
        step_result = StepResult(
            step_id=task.step_id,
            kind="search",
            tool_name="search_notes",
            query=task.query,
            status="success",
            result_count=len(results),
            results=[to_search_hit(result) for result in results],
            sources=format_sources(results) if results else [],
            reason=task.reason,
        )
        return {
            "step_results": [step_result],
            "graph_path": [f"search_worker:{task.step_id}"],
            "node_retry_counts": {attempt_key: attempt},
            "trace": [
                AdvancedTraceStep(
                    node_name="search_worker",
                    kind="retry_policy" if attempt > 1 else "send",
                    detail=f"并行任务 {task.step_id} 第 {attempt} 次节点执行完成，获得 {len(results)} 条结果。",
                    metadata={"task_id": task.step_id, "attempt": attempt, "result_count": len(results)},
                )
            ],
        }

    def _evidence_check_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        tasks = state.get("search_tasks", [])
        all_results = [*state.get("step_results", []), *state.get("retry_step_results", [])]
        missing_tasks = [task for task in tasks if not _task_has_evidence(task, all_results)]
        result = EvidenceCheckResult(
            is_sufficient=not missing_tasks,
            missing_points=[f"{task.step_id} 没有检索到证据：{task.query}" for task in missing_tasks],
            suggested_queries=[f"{task.query} 使用方法 注意事项" for task in missing_tasks],
            checked_step_ids=[task.step_id for task in tasks],
            missing_step_ids=[task.step_id for task in missing_tasks],
            retry_count=state.get("business_retry_count", 0),
            reason="所有并行检索任务都有证据。" if not missing_tasks else "部分并行检索任务没有证据。",
        )
        return {
            "evidence_check": result,
            "graph_path": ["evidence_check"],
            "trace": [
                AdvancedTraceStep(
                    node_name="evidence_check",
                    kind="evidence",
                    detail=result.reason,
                    metadata={"missing_step_ids": result.missing_step_ids},
                )
            ],
        }

    def _route_evidence_node(self, state: AdvancedAgentState) -> Command:
        request = state["request"]
        evidence = state["evidence_check"]
        retry_count = state.get("business_retry_count", 0)
        should_retry = bool(evidence.missing_step_ids) and retry_count < request.max_retries
        destination = "dispatch_retry" if should_retry else "build_context"
        reason = (
            "Evidence 不足且仍有业务补搜额度。"
            if should_retry
            else "Evidence 已充分，或业务补搜额度已用完。"
        )
        update: dict[str, Any] = {
            "graph_path": ["route_evidence"],
            "route_decisions": [RouteDecision(node_name="route_evidence", destination=destination, reason=reason)],
            "trace": [AdvancedTraceStep(node_name="route_evidence", kind="command", detail=reason)],
        }
        if should_retry:
            update["business_retry_count"] = retry_count + 1
        return Command(goto=destination, update=update)

    def _dispatch_retry_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        missing_ids = state["evidence_check"].missing_step_ids
        return {
            "graph_path": ["dispatch_retry"],
            "trace": [
                AdvancedTraceStep(
                    node_name="dispatch_retry",
                    kind="send",
                    detail=f"对 {len(missing_ids)} 个缺失证据点再次并行 Send。",
                    metadata={"missing_step_ids": missing_ids},
                )
            ],
        }

    def _send_retry_tasks(self, state: AdvancedAgentState) -> list[Send]:
        missing_ids = set(state["evidence_check"].missing_step_ids)
        retry_count = state.get("business_retry_count", 1)
        return [
            Send(
                "retry_search_worker",
                {
                    "request": state["request"],
                    "run_id": state["run_id"],
                    "thread_id": state["thread_id"],
                    "active_task": task,
                    "business_retry_count": retry_count,
                },
            )
            for task in state.get("search_tasks", [])
            if task.step_id in missing_ids
        ]

    def _retry_search_worker_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        request = state["request"]
        task = state["active_task"]
        retry_count = state.get("business_retry_count", 1)
        query = f"{task.query} 使用方法 注意事项"
        attempt_key = f"{state['run_id']}:{task.step_id}:business_retry_{retry_count}"
        attempt = self._next_attempt(attempt_key)
        results = list(
            self.retrieval_service.search(
                query,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
            )
        )
        result = StepResult(
            step_id=f"retry_{task.step_id}_{retry_count}",
            kind="search",
            tool_name="search_notes",
            query=query,
            status="success",
            result_count=len(results),
            results=[to_search_hit(item) for item in results],
            sources=format_sources(results) if results else [],
            reason=f"业务 Evidence retry：{task.step_id}",
        )
        return {
            "retry_step_results": [result],
            "graph_path": [f"retry_search_worker:{task.step_id}"],
            "node_retry_counts": {attempt_key: attempt},
            "trace": [
                AdvancedTraceStep(
                    node_name="retry_search_worker",
                    kind="evidence",
                    detail=f"业务补搜 {task.step_id} 返回 {len(results)} 条结果。",
                    metadata={"query": query, "result_count": len(results)},
                )
            ],
        }

    def _build_context_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        request = state["request"]
        builder = self.context_builder or ContextBuilder(
            max_chunks=request.context_max_chunks,
            token_budget=request.context_token_budget,
        )
        evidence = state.get("evidence_check") or _empty_evidence_check()
        bundle = builder.build(
            question=request.question,
            plan=state["plan"],
            step_results=state.get("step_results", []),
            retry_step_results=state.get("retry_step_results", []),
            evidence_check=evidence,
            memory_snapshot=state["memory_snapshot"],
        )
        step_results = [*state.get("step_results", []), *state.get("retry_step_results", [])]
        sources = _dedupe(source for result in step_results for source in result.sources)
        used_retrieval = any(result.result_count > 0 for result in step_results)
        return {
            "context_bundle": bundle,
            "sources": sources,
            "used_retrieval": used_retrieval,
            "graph_path": ["build_context"],
            "trace": [
                AdvancedTraceStep(
                    node_name="build_context",
                    kind="context",
                    detail=bundle.context_summary,
                    metadata={"included_chunks": len(bundle.included_chunks)},
                )
            ],
        }

    def _answer_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        bundle = state["context_bundle"]
        chunks = []
        for chunk in self.chat_model.stream(_to_langchain_messages(bundle.messages)):
            text = _message_text(chunk.content)
            if text:
                chunks.append(text)
        answer = "".join(chunks).strip()
        if not answer:
            answer = _fallback_non_stream_answer(state)
        return {
            "answer": answer,
            "graph_path": ["answer"],
            "trace": [
                AdvancedTraceStep(
                    node_name="answer",
                    kind="messages",
                    detail="Answer ChatModel 已通过 messages stream 生成最终答案。",
                    metadata={"answer_length": len(answer)},
                )
            ],
        }

    def _save_memory_node(self, state: AdvancedAgentState) -> dict[str, Any]:
        try:
            result = self.memory_store.append_turn(
                conversation_id=state["conversation_id"],
                user_message=state["request"].question,
                assistant_message=state.get("answer", ""),
                sources=list(state.get("sources", [])),
                tool_calls=_tool_call_records([*state.get("step_results", []), *state.get("retry_step_results", [])]),
            )
            detail = "最终答案已写入 MySQL Conversation Memory。"
        except Exception as exc:
            result = MemoryWriteResult(
                conversation_id=state["conversation_id"],
                saved=False,
                reason=str(exc),
            )
            detail = "写入 MySQL Conversation Memory 失败。"
        return {
            "memory_write": result,
            "graph_path": ["save_memory"],
            "trace": [
                AdvancedTraceStep(
                    node_name="save_memory",
                    kind="memory",
                    detail=detail,
                    metadata={"saved": result.saved, "turn_id": result.turn_id},
                )
            ],
        }

    def _initial_state(
        self,
        request: AdvancedAskRequest,
        run_id: str,
        thread_id: str,
    ) -> AdvancedAgentState:
        return {
            "request": request,
            "run_id": run_id,
            "thread_id": thread_id,
            "conversation_id": request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}",
            "planner_subgraph_path": [],
            "planner_trace": [],
            "step_results": [],
            "retry_step_results": [],
            "business_retry_count": 0,
            "graph_path": [],
            "trace": [],
            "route_decisions": [],
            "node_retry_counts": {},
            "sources": [],
            "used_retrieval": False,
            "answer": "",
        }

    def _response_from_state(
        self,
        state: dict[str, Any],
        request: AdvancedAskRequest,
        run_id: str,
        thread_id: str,
    ) -> AdvancedAskResponse:
        history_count = sum(1 for _ in self.graph.get_state_history(self._config(thread_id)))
        plan = state.get("plan") or _clarify_plan("Advanced Graph 没有生成计划。")
        return AdvancedAskResponse(
            run_id=run_id,
            thread_id=thread_id,
            conversation_id=state.get("conversation_id") or request.conversation_id or "unknown",
            question=request.question,
            answer=state.get("answer") or "执行结束，但没有生成答案。",
            used_retrieval=bool(state.get("used_retrieval")),
            sources=list(state.get("sources", [])),
            plan=plan,
            planner_subgraph_path=list(state.get("planner_subgraph_path", [])),
            graph_path=list(state.get("graph_path", [])),
            step_results=list(state.get("step_results", [])),
            retry_step_results=list(state.get("retry_step_results", [])),
            evidence_check=state.get("evidence_check") or _empty_evidence_check(),
            context_bundle=state.get("context_bundle") or _empty_context_bundle(request),
            memory_snapshot=state.get("memory_snapshot") or _empty_memory_snapshot(
                state.get("conversation_id") or "unknown",
                request.memory_window,
            ),
            memory_compaction=state.get("memory_compaction") or MemoryCompactionResult(
                conversation_id=state.get("conversation_id") or "unknown",
                reason="没有执行 Memory Compaction。",
            ),
            memory_write=state.get("memory_write") or MemoryWriteResult(
                conversation_id=state.get("conversation_id") or "unknown",
                saved=False,
                reason="没有执行 Memory write。",
            ),
            trace=[*state.get("planner_trace", []), *state.get("trace", [])],
            route_decisions=list(state.get("route_decisions", [])),
            node_retry_counts=dict(state.get("node_retry_counts", {})),
            parallel_task_count=len(state.get("search_tasks", [])),
            state_history_count=history_count,
            stream_modes=list(STREAM_MODES),
        )

    def _next_attempt(self, key: str) -> int:
        with self._attempt_lock:
            attempt = self._attempts.get(key, 0) + 1
            self._attempts[key] = attempt
            return attempt

    def _clear_attempts(self, run_id: str) -> None:
        prefix = f"{run_id}:"
        with self._attempt_lock:
            self._attempts = {key: value for key, value in self._attempts.items() if not key.startswith(prefix)}

    @staticmethod
    def _config(thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}


def _normalize_stream_item(item: dict[str, Any]) -> dict[str, Any] | None:
    event_type = item.get("type")
    namespace = list(item.get("ns") or ())
    if event_type == "messages":
        message, metadata = item["data"]
        content = _message_text(message.content)
        if not content:
            return None
        return {
            "name": "answer_delta",
            "detail": "Answer messages stream 产生可见文本增量。",
            "data": {
                "delta": content,
                "node_name": metadata.get("langgraph_node"),
                "namespace": namespace,
            },
        }
    if event_type == "custom":
        data = dict(item.get("data") or {})
        return {
            "name": str(data.get("kind") or "custom_event"),
            "detail": str(data.get("detail") or "LangGraph custom stream event。"),
            "data": {**data, "namespace": namespace},
        }
    if event_type == "updates":
        updates = item.get("data") or {}
        return {
            "name": "graph_update",
            "detail": f"LangGraph 完成状态更新：{', '.join(updates.keys()) or 'unknown'}。",
            "data": {
                "nodes": list(updates.keys()),
                "updated_keys": {name: sorted((value or {}).keys()) for name, value in updates.items()},
                "namespace": namespace,
            },
        }
    return None


def _task_has_evidence(task: SearchTask, results: list[StepResult]) -> bool:
    return any(
        result.result_count > 0
        and (result.step_id == task.step_id or result.step_id.startswith(f"retry_{task.step_id}_"))
        for result in results
    )


def _to_langchain_messages(messages: list[dict[str, str]]):
    converted = []
    for message in messages:
        if message.get("role") == "system":
            converted.append(SystemMessage(content=message.get("content", "")))
        else:
            converted.append(HumanMessage(content=message.get("content", "")))
    return converted


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return ""


def _fallback_non_stream_answer(state: AdvancedAgentState) -> str:
    for step in state.get("plan", _clarify_plan("没有计划。")).steps:
        if step.instruction:
            return step.instruction
    chunks = state.get("context_bundle", _empty_context_bundle(state["request"])).included_chunks
    if chunks:
        return f"模型没有返回流式文本。首条证据：{chunks[0].text_preview}"
    return "模型没有返回流式文本，请补充更明确的问题。"


def _tool_call_records(results: list[StepResult]) -> list[dict[str, Any]]:
    return [
        {
            "step_id": result.step_id,
            "tool_name": result.tool_name,
            "query": result.query,
            "status": result.status,
            "result_count": result.result_count,
        }
        for result in results
        if result.tool_name
    ]


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _empty_evidence_check() -> EvidenceCheckResult:
    return EvidenceCheckResult(is_sufficient=True, retry_count=0, reason="计划没有 search task，不需要证据检查。")


def _empty_memory_snapshot(conversation_id: str, window: int) -> MemorySnapshot:
    return MemorySnapshot(conversation_id=conversation_id, window=window)


def _empty_context_bundle(request: AdvancedAskRequest) -> ContextBundle:
    return ContextBundle(
        messages=[],
        included_chunks=[],
        excluded_chunks=[],
        token_budget=request.context_token_budget,
        context_summary="尚未构建 Answer Context。",
    )


def _clarify_plan(reason: str) -> Plan:
    return Plan(
        goal="澄清用户问题",
        steps=[PlanStep(id="s1", kind="clarify", instruction="请补充更明确的问题范围。", reason=reason)],
    )
