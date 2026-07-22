from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal, TypedDict


from langgraph.graph import END, START, StateGraph

from obsidian_rag.prompting import format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.core.compaction import ConversationCompactor
from obsidian_rag.core.collections.protocol import RetrievalScopeResolver
from obsidian_rag.core.collections.schemas import RetrievalScope, RetrievalScopeRequest
from obsidian_rag.core.context import ContextBuilder, build_memory_aware_planner_question
from obsidian_rag.core.llm import ChatStreamDelta
from obsidian_rag.core.mysql_memory import MySQLConversationMemoryStore
from obsidian_rag.core.planner import PlannerService
from obsidian_rag.core.permissions.policy import PermissionPolicy
from obsidian_rag.core.permissions.schemas import PermissionDecision, PermissionPrincipal, PermissionReport
from obsidian_rag.core.skills.protocol import SkillResolver
from obsidian_rag.core.skills.registry import build_skills_context
from obsidian_rag.core.skills.schemas import SkillDocument, SkillLoadedSummary, SkillManifest, SkillSelection
from obsidian_rag.core.schemas import (
    Plan,
    PlanRequest,
    PlanStep,
    PlannerToolDefinition,
    AgentAskRequest,
    AgentAskResponse,
    AnswerStreamMetrics,
    AgentNodeTiming,
    AgentProgressEvent,
    AgentProgressPhase,
    AgentTraceStep,
    ContextBundle,
    EvidenceCheckResult,
    MemorySnapshot,
    MemoryCompactionResult,
    MemoryWriteResult,
    StepResult,
)
from obsidian_rag.core.tools import ToolRegistry, build_search_tool_registry


SearchLikeResult = SearchResult | RankedSearchResult
EventSink = Callable[[str, dict[str, Any]], None]
_ACTIVE_EVENT_SINK: ContextVar[EventSink | None] = ContextVar("agent_event_sink", default=None)
_NODE_PROGRESS_PHASE: dict[str, AgentProgressPhase] = {
    "load_memory": "memory",
    "compact_memory": "memory",
    "discover_skills": "skill",
    "skill_router": "skill",
    "load_skill": "skill",
    "planner": "planning",
    "resolve_retrieval_scope": "routing",
    "authorize_steps": "authorization",
    "execute_steps": "retrieval",
    "retry_search": "retrieval",
    "evidence_check": "evidence",
    "build_context": "context",
    "synthesize_answer": "answer",
    "save_memory": "memory_write",
}


class AgentState(TypedDict, total=False):
    run_id: str
    conversation_id: str
    request: AgentAskRequest
    memory_snapshot: MemorySnapshot
    memory_compaction: MemoryCompactionResult
    memory_write: MemoryWriteResult
    plan: Plan
    step_results: list[StepResult]
    retry_step_results: list[StepResult]
    evidence_check: EvidenceCheckResult
    context_bundle: ContextBundle
    search_results: list[SearchLikeResult]
    answer: str
    used_retrieval: bool
    sources: list[str]
    retry_count: int
    attempted_queries: list[str]
    graph_path: list[str]
    trace: list[AgentTraceStep]
    node_timings: list[AgentNodeTiming]
    answer_stream: AnswerStreamMetrics
    tool_catalog: list[PlannerToolDefinition]
    retrieval_scope: RetrievalScope
    permission_report: PermissionReport
    skill_candidates: list[SkillManifest]
    skill_selection: SkillSelection
    loaded_skill: SkillDocument
    loaded_skills: list[SkillDocument]
    skill_context: str


class AgentService:
    def __init__(
        self,
        retrieval_service,
        planner_service: PlannerService | None = None,
        chat_client=None,
        chat_client_factory=None,
        tool_registry: ToolRegistry | None = None,
        context_builder: ContextBuilder | None = None,
        memory_store: MySQLConversationMemoryStore | None = None,
        memory_compactor: ConversationCompactor | None = None,
        retrieval_scope_resolver: RetrievalScopeResolver | None = None,
        permission_policy: PermissionPolicy | None = None,
        skill_resolver: SkillResolver | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.planner_service = planner_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory
        self.tool_registry = tool_registry or build_search_tool_registry(retrieval_service)
        self.context_builder = context_builder
        self.memory_store = memory_store or MySQLConversationMemoryStore()
        self.memory_compactor = memory_compactor
        self.retrieval_scope_resolver = retrieval_scope_resolver
        self.permission_policy = permission_policy
        self.skill_resolver = skill_resolver
        self.graph = self._build_graph()

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        final_state = self.graph.invoke(self._initial_state(request))
        return self._response_from_state(final_state, request)

    def ask_with_events(
        self,
        request: AgentAskRequest,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> AgentAskResponse:
        """以 LangGraph values stream 执行，并向可选 sink 发布可观察事实事件。

        事件只包含节点、工具、结果数量和原因，不包含模型内部推理过程。
        未提供 sink 时行为等同于普通 `ask()`，便于旧版本继续复用 AgentService。
        """

        token = _ACTIVE_EVENT_SINK.set(event_sink)
        try:
            return self._ask_with_events(request, event_sink)
        finally:
            _ACTIVE_EVENT_SINK.reset(token)

    def _ask_with_events(
        self,
        request: AgentAskRequest,
        event_sink: EventSink | None,
    ) -> AgentAskResponse:
        final_state: AgentState | None = None
        trace_cursor = 0
        for state in self.graph.stream(self._initial_state(request), stream_mode="values"):
            final_state = state
            graph_path = state.get("graph_path", [])
            node_name = graph_path[-1] if graph_path else None
            if node_name:
                node_timing = next(
                    (timing for timing in reversed(state.get("node_timings", [])) if timing.node_name == node_name),
                    None,
                )
                _emit_agent_event(
                    event_sink,
                    "node_finished",
                    {
                        "node_name": node_name,
                        "graph_path": list(graph_path),
                        "started_at": node_timing.started_at if node_timing else None,
                        "finished_at": node_timing.finished_at if node_timing else None,
                        "duration_ms": node_timing.duration_ms if node_timing else None,
                    },
                )
                _emit_progress_event(
                    event_sink,
                    node_name=node_name,
                    status="completed",
                    state=state,
                    retrieval_service=self.retrieval_service,
                )

            traces = state.get("trace", [])
            for trace in traces[trace_cursor:]:
                _emit_agent_event(
                    event_sink,
                    "trace_event",
                    {
                        "node_name": trace.node_name,
                        "step_type": trace.step_type,
                        "step_id": trace.step_id,
                        "tool_name": trace.tool_name,
                        "query": trace.query,
                        "result_count": trace.result_count,
                        "reason": trace.reason,
                        "metadata": trace.metadata,
                    },
                )
            trace_cursor = len(traces)

        if final_state is None:
            raise RuntimeError("Agent graph 没有产生最终状态。")
        return self._response_from_state(final_state, request)

    def _initial_state(self, request: AgentAskRequest) -> AgentState:
        return {
            "run_id": f"run_{uuid.uuid4().hex[:12]}",
            "conversation_id": request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}",
            "request": request,
            "step_results": [],
            "retry_step_results": [],
            "search_results": [],
            "answer": "",
            "used_retrieval": False,
            "sources": [],
            "retry_count": 0,
            "attempted_queries": [],
            "graph_path": [],
            "trace": [],
            "node_timings": [],
            "answer_stream": AnswerStreamMetrics(mode="complete"),
            "tool_catalog": [],
            "skill_candidates": [],
        }

    def _response_from_state(self, final_state: AgentState, request: AgentAskRequest) -> AgentAskResponse:
        return AgentAskResponse(
            run_id=final_state["run_id"],
            conversation_id=final_state["conversation_id"],
            question=request.question,
            collection=_response_collection_name(
                self.retrieval_service,
                request.collection,
                final_state.get("retrieval_scope"),
            ),
            answer=final_state.get("answer") or "执行结束，但没有生成最终答案。",
            used_retrieval=bool(final_state.get("used_retrieval", False)),
            sources=final_state.get("sources", []),
            plan=Plan.model_validate(_model_data(final_state["plan"])),
            tool_catalog=[
                PlannerToolDefinition.model_validate(_model_data(item))
                for item in final_state.get("tool_catalog", [])
            ],
            retrieval_scope=(
                RetrievalScope.model_validate(_model_data(final_state["retrieval_scope"]))
                if final_state.get("retrieval_scope")
                else None
            ),
            permission_report=(
                PermissionReport.model_validate(_model_data(final_state["permission_report"]))
                if final_state.get("permission_report")
                else None
            ),
            skill_selection=(
                SkillSelection.model_validate(_model_data(final_state["skill_selection"]))
                if final_state.get("skill_selection")
                else None
            ),
            loaded_skill=(
                SkillLoadedSummary.from_document(
                    SkillDocument.model_validate(_model_data(final_state["loaded_skill"]))
                )
                if final_state.get("loaded_skill")
                else None
            ),
            loaded_skills=[
                SkillLoadedSummary.from_document(SkillDocument.model_validate(_model_data(item)))
                for item in final_state.get("loaded_skills", [])
            ],
            step_results=[StepResult.model_validate(_model_data(item)) for item in final_state.get("step_results", [])],
            retry_step_results=[
                StepResult.model_validate(_model_data(item)) for item in final_state.get("retry_step_results", [])
            ],
            evidence_check=EvidenceCheckResult.model_validate(
                _model_data(final_state.get("evidence_check") or _empty_evidence_check())
            ),
            context_bundle=ContextBundle.model_validate(
                _model_data(final_state.get("context_bundle") or _empty_context_bundle(request))
            ),
            memory_snapshot=MemorySnapshot.model_validate(
                _model_data(
                    final_state.get("memory_snapshot")
                    or _empty_memory_snapshot(final_state["conversation_id"], request.memory_window)
                )
            ),
            memory_compaction=MemoryCompactionResult.model_validate(
                _model_data(
                    final_state.get("memory_compaction")
                    or _empty_memory_compaction(final_state["conversation_id"])
                )
            ),
            memory_write=MemoryWriteResult.model_validate(
                _model_data(
                    final_state.get("memory_write")
                    or MemoryWriteResult(
                        conversation_id=final_state["conversation_id"],
                        saved=False,
                        reason="没有执行 memory write。",
                    )
                )
            ),
            graph_path=final_state.get("graph_path", []),
            trace=final_state.get("trace", []),
            node_timings=final_state.get("node_timings", []),
            answer_stream=final_state.get("answer_stream") or AnswerStreamMetrics(mode="complete"),
        )

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("load_memory", self._timed_node("load_memory", self._load_memory_node))
        graph.add_node("compact_memory", self._timed_node("compact_memory", self._compact_memory_node))
        if self.skill_resolver is not None:
            graph.add_node("discover_skills", self._timed_node("discover_skills", self._discover_skills_node))
            graph.add_node("skill_router", self._timed_node("skill_router", self._skill_router_node))
            graph.add_node("load_skill", self._timed_node("load_skill", self._load_skill_node))
        graph.add_node("planner", self._timed_node("planner", self._planner_node))
        if self.retrieval_scope_resolver is not None:
            graph.add_node(
                "resolve_retrieval_scope",
                self._timed_node("resolve_retrieval_scope", self._resolve_retrieval_scope_node),
            )
        if self.permission_policy is not None:
            graph.add_node(
                "authorize_steps",
                self._timed_node("authorize_steps", self._authorize_steps_node),
            )
        graph.add_node("execute_steps", self._timed_node("execute_steps", self._execute_steps_node))
        graph.add_node("evidence_check", self._timed_node("evidence_check", self._evidence_check_node))
        graph.add_node("retry_search", self._timed_node("retry_search", self._retry_search_node))
        graph.add_node("build_context", self._timed_node("build_context", self._build_context_node))
        graph.add_node("synthesize_answer", self._timed_node("synthesize_answer", self._synthesize_answer_node))
        graph.add_node("save_memory", self._timed_node("save_memory", self._save_memory_node))

        graph.add_edge(START, "load_memory")
        graph.add_edge("load_memory", "compact_memory")
        if self.skill_resolver is not None:
            graph.add_edge("compact_memory", "discover_skills")
            graph.add_edge("discover_skills", "skill_router")
            graph.add_edge("skill_router", "load_skill")
            graph.add_edge("load_skill", "planner")
        else:
            graph.add_edge("compact_memory", "planner")
        if self.retrieval_scope_resolver is not None:
            graph.add_edge("planner", "resolve_retrieval_scope")
            graph.add_edge(
                "resolve_retrieval_scope",
                "authorize_steps" if self.permission_policy is not None else "execute_steps",
            )
        else:
            graph.add_edge("planner", "authorize_steps" if self.permission_policy is not None else "execute_steps")
        if self.permission_policy is not None:
            graph.add_edge("authorize_steps", "execute_steps")
        graph.add_edge("execute_steps", "evidence_check")
        graph.add_conditional_edges(
            "evidence_check",
            _route_after_evidence_check,
            {"retry_search": "retry_search", "build_context": "build_context"},
        )
        graph.add_edge("retry_search", "evidence_check")
        graph.add_edge("build_context", "synthesize_answer")
        graph.add_edge("synthesize_answer", "save_memory")
        graph.add_edge("save_memory", END)
        return graph.compile()

    def _timed_node(self, node_name: str, handler):
        def run(state: AgentState) -> AgentState:
            _emit_progress_event(
                _ACTIVE_EVENT_SINK.get(),
                node_name=node_name,
                status="running",
                state=state,
                retrieval_service=self.retrieval_service,
            )
            started_at = _now()
            started = perf_counter()
            try:
                result = handler(state)
            except Exception as exc:
                _emit_progress_event(
                    _ACTIVE_EVENT_SINK.get(),
                    node_name=node_name,
                    status="failed",
                    state=state,
                    retrieval_service=self.retrieval_service,
                    metadata={"error_type": type(exc).__name__},
                )
                raise
            finished_at = _now()
            timings = list(result.get("node_timings", []))
            timings.append(
                AgentNodeTiming(
                    node_name=node_name,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=max(0, round((perf_counter() - started) * 1000)),
                )
            )
            result["node_timings"] = timings
            return result

        return run

    def _load_memory_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("load_memory")
        request = state["request"]
        snapshot = self.memory_store.load_snapshot(state["conversation_id"], window=request.memory_window)
        state["memory_snapshot"] = snapshot
        state["trace"].append(
            AgentTraceStep(
                node_name="load_memory",
                step_type="memory_read",
                result_count=snapshot.loaded_turn_count,
                reason=f"读取最近 {snapshot.loaded_turn_count} 轮对话，省略 {snapshot.omitted_turn_count} 轮。",
                metadata={
                    "conversation_id": state["conversation_id"],
                    "window": snapshot.window,
                    "total_turn_count": snapshot.total_turn_count,
                },
            )
        )
        return state

    def _discover_skills_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("discover_skills")
        candidates = self.skill_resolver.list_manifests() if self.skill_resolver is not None else []
        state["skill_candidates"] = candidates
        state["trace"].append(
            AgentTraceStep(
                node_name="discover_skills",
                step_type="skill",
                result_count=len(candidates),
                reason=f"Skill Registry 发现 {len(candidates)} 个候选 Skill。",
                metadata={
                    "candidate_names": [item.name for item in candidates],
                    "registry_errors": self.skill_resolver.errors if self.skill_resolver is not None else [],
                },
            )
        )
        return state

    def _skill_router_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("skill_router")
        request = state["request"]
        if self.skill_resolver is None:
            selection = SkillSelection(status="disabled", reason="未注入 SkillResolver。")
        else:
            selection = self.skill_resolver.select(
                question=request.question,
                candidates=state.get("skill_candidates", []),
                skill_name=getattr(request, "skill_name", None),
                skill_names=list(getattr(request, "skill_names", []) or []),
                selection_mode=getattr(request, "skill_selection_mode", "augment"),
                router_enabled=bool(getattr(request, "skill_router_enabled", True)),
            )
        state["skill_selection"] = selection
        state["trace"].append(
            AgentTraceStep(
                node_name="skill_router",
                step_type="skill",
                result_count=len(selection.selected_skills or ([selection.selected_skill] if selection.selected_skill else [])),
                reason=selection.reason,
                metadata={
                    "status": selection.status,
                    "selected_skill": selection.selected_skill,
                    "selected_skills": selection.selected_skills,
                    "explicit_skills": selection.explicit_skills,
                    "implicit_skills": selection.implicit_skills,
                    "router_called": selection.router_called,
                    "routing_decision": (
                        selection.routing_decision.model_dump() if selection.routing_decision else None
                    ),
                    "confidence": selection.confidence,
                    "candidate_names": selection.candidate_names,
                },
            )
        )
        return state

    def _load_skill_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("load_skill")
        selection = state.get("skill_selection")
        selected_skills = list(selection.selected_skills) if selection else []
        if not selected_skills and selection and selection.selected_skill:
            selected_skills = [selection.selected_skill]
        if not selected_skills or self.skill_resolver is None:
            state["trace"].append(
                AgentTraceStep(
                    node_name="load_skill",
                    step_type="skill",
                    result_count=0,
                    reason="本轮没有选中 Skill，不向 Planner 注入方法上下文。",
                )
            )
            return state
        documents: list[SkillDocument] = []
        load_errors: list[str] = []
        for selected_skill in selected_skills:
            try:
                documents.append(self.skill_resolver.load(selected_skill))
            except (KeyError, OSError, ValueError) as exc:
                load_errors.append(f"{selected_skill}: {exc}")
        if not documents:
            state["skill_selection"] = selection.model_copy(
                update={
                    "status": "router_error",
                    "selected_skill": None,
                    "selected_skills": [],
                    "reason": f"Skill 加载失败，已跳过方法注入：{'; '.join(load_errors)}",
                }
            )
            state["trace"].append(
                AgentTraceStep(
                    node_name="load_skill",
                    step_type="error",
                    result_count=0,
                    reason=state["skill_selection"].reason,
                    metadata={"load_errors": load_errors},
                )
            )
            return state
        state["loaded_skill"] = documents[0]
        state["loaded_skills"] = documents
        state["skill_context"] = build_skills_context(state["request"].question, documents)
        state["trace"].append(
            AgentTraceStep(
                node_name="load_skill",
                step_type="skill",
                result_count=len(documents),
                reason=f"已加载 {len(documents)} 个 Skills 并准备注入 Planner Context。",
                metadata={
                    "selected_skills": [document.name for document in documents],
                    "paths": [document.path for document in documents],
                    "estimated_tokens": sum(document.estimated_tokens for document in documents),
                    "load_errors": load_errors,
                },
            )
        )
        return state

    def _compact_memory_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("compact_memory")
        request = state["request"]
        if not request.memory_compaction_enabled:
            result = MemoryCompactionResult(
                conversation_id=state["conversation_id"],
                reason="本次请求关闭了 Memory Compaction。",
            )
        else:
            compactor = self.memory_compactor or ConversationCompactor(
                memory_store=self.memory_store,
                chat_client_factory=self._chat_client,
            )
            result = compactor.compact(
                conversation_id=state["conversation_id"],
                keep_recent_turns=request.memory_window,
                trigger_turns=request.memory_compaction_trigger_turns,
                trigger_tokens=request.memory_compaction_trigger_tokens,
            )
            if result.compacted:
                state["memory_snapshot"] = self.memory_store.load_snapshot(
                    state["conversation_id"],
                    window=request.memory_window,
                )

        state["memory_compaction"] = result
        state["trace"].append(
            AgentTraceStep(
                node_name="compact_memory",
                step_type="memory_compaction",
                result_count=result.summarized_turn_count,
                reason=result.reason,
                metadata={
                    "attempted": result.attempted,
                    "compacted": result.compacted,
                    "candidate_turn_count": result.candidate_turn_count,
                    "estimated_input_tokens": result.estimated_input_tokens,
                    "summary_through_turn_id": result.summary_through_turn_id,
                },
            )
        )
        return state

    def _planner_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        request = state["request"]
        state["graph_path"].append("planner")
        planner = self._planner_service()
        planner_question = build_memory_aware_planner_question(
            request.question,
            state.get("memory_snapshot")
            or _empty_memory_snapshot(state["conversation_id"], request.memory_window),
            state.get("skill_context"),
        )
        planner_response = planner.plan(
            PlanRequest(
                question=planner_question,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
                max_steps=request.max_steps,
            )
        )
        state["plan"] = planner_response.plan
        state["trace"].append(
            AgentTraceStep(
                node_name="planner",
                step_type="planner",
                reason="Planner 生成可执行计划。",
                metadata={"planner_graph_path": planner_response.graph_path, "step_count": len(planner_response.plan.steps)},
            )
        )
        return state

    def _execute_steps_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("execute_steps")
        request = state["request"]
        step_results: list[StepResult] = []
        search_results: list[SearchLikeResult] = []

        for step in state["plan"].steps:
            blocked = _permission_blocked_step_result(step, state.get("permission_report"))
            if blocked is not None:
                result = blocked
            elif step.kind == "search":
                result = self._execute_search_step(step, request, state.get("retrieval_scope"))
                search_results.extend(_search_results_from_step_result(result))
            else:
                result = _non_search_step_result(step)
            step_results.append(result)
            state["trace"].append(
                AgentTraceStep(
                    node_name="execute_steps",
                    step_type="tool_result" if result.status != "failed" else "error",
                    step_id=step.id,
                    tool_name=result.tool_name,
                    query=result.query,
                    result_count=result.result_count,
                    reason=result.reason or result.error,
                    metadata={**result.metadata, **_rerank_metadata_from_step_result(result)},
                )
            )

        state["step_results"] = step_results
        state["search_results"] = search_results
        state["used_retrieval"] = bool(search_results)
        state["sources"] = format_sources(search_results) if search_results else []
        return state

    def _authorize_steps_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("authorize_steps")
        request = state["request"]
        principal = PermissionPrincipal.model_validate(
            _model_data(getattr(request, "principal", None) or PermissionPrincipal())
        )
        report = self.permission_policy.authorize(
            plan=state["plan"],
            principal=principal,
            tool_registry=self.tool_registry,
            retrieval_scope=state.get("retrieval_scope"),
            run_id=state["run_id"],
            conversation_id=state["conversation_id"],
        )
        state["permission_report"] = report
        state["trace"].append(
            AgentTraceStep(
                node_name="authorize_steps",
                step_type="permission",
                result_count=len(report.decisions),
                reason=report.summary,
                metadata={
                    "allow_count": report.allow_count,
                    "confirm_count": report.confirm_count,
                    "deny_count": report.deny_count,
                    "all_allowed": report.all_allowed,
                },
            )
        )
        return state

    def _resolve_retrieval_scope_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("resolve_retrieval_scope")
        request = state["request"]
        search_required = any(step.kind == "search" for step in state["plan"].steps)
        if not search_required:
            scope = RetrievalScope(
                status="not_required",
                reason="Planner 没有生成 search step，本轮不解析知识库范围。",
            )
        elif self.retrieval_scope_resolver is None:
            scope = RetrievalScope(
                status="disabled",
                selected_collections=[_effective_collection_name(self.retrieval_service, request.collection)],
                reason="没有注入 RetrievalScopeResolver，使用单 Collection 兼容路径。",
            )
        else:
            scope = self.retrieval_scope_resolver.resolve(
                RetrievalScopeRequest(
                    question=request.question,
                    explicit_collection=request.collection,
                    router_enabled=bool(getattr(request, "collection_router_enabled", True)),
                    max_collections=int(getattr(request, "max_collections", 2)),
                )
            )
        state["retrieval_scope"] = scope
        state["trace"].append(
            AgentTraceStep(
                node_name="resolve_retrieval_scope",
                step_type="collection_routing",
                result_count=len(scope.selected_collections),
                reason=scope.reason,
                metadata={
                    "status": scope.status,
                    "candidate_ids": scope.candidate_ids,
                    "selected_ids": scope.selected_ids,
                    "selected_collections": scope.selected_collections,
                    "confidence": scope.confidence,
                    "errors": scope.errors,
                },
            )
        )
        return state

    def _evidence_check_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("evidence_check")
        evidence_check = _check_evidence(
            step_results=state.get("step_results", []),
            retry_step_results=state.get("retry_step_results", []),
            retry_count=state.get("retry_count", 0),
            attempted_queries=state.get("attempted_queries", []),
        )
        state["evidence_check"] = evidence_check
        state["trace"].append(
            AgentTraceStep(
                node_name="evidence_check",
                step_type="evidence_check",
                result_count=len(state.get("search_results", [])),
                reason=evidence_check.reason,
                metadata={
                    "is_sufficient": evidence_check.is_sufficient,
                    "missing_step_ids": evidence_check.missing_step_ids,
                    "suggested_queries": evidence_check.suggested_queries,
                    "retry_count": evidence_check.retry_count,
                },
            )
        )
        return state

    def _retry_search_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("retry_search")
        request = state["request"]
        evidence_check = state["evidence_check"]
        retry_count = state.get("retry_count", 0) + 1
        retry_results = list(state.get("retry_step_results", []))
        search_results = list(state.get("search_results", []))
        attempted_queries = list(state.get("attempted_queries", []))

        for index, query in enumerate(evidence_check.suggested_queries, start=1):
            if query in attempted_queries:
                continue
            original_step_id = evidence_check.missing_step_ids[index - 1] if index <= len(evidence_check.missing_step_ids) else "unknown"
            permission_decision = _permission_decision_for_step(state.get("permission_report"), original_step_id)
            if permission_decision is not None and permission_decision.decision != "allow":
                retry_results.append(
                    StepResult(
                        step_id=f"retry_{original_step_id}_{retry_count}",
                        kind="search",
                        tool_name="search_notes",
                        query=query,
                        status="skipped" if permission_decision.decision == "confirm" else "failed",
                        error=permission_decision.reason,
                        reason=f"补搜未执行：原步骤权限决定为 {permission_decision.decision}。",
                        metadata={"permission": permission_decision.model_dump()},
                    )
                )
                attempted_queries.append(query)
                continue
            tool_result = self.tool_registry.run(
                "search_notes",
                query=query,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
                **_retrieval_scope_kwargs(state.get("retrieval_scope"), request.collection),
            )
            results = list(tool_result.results)
            step_result = StepResult(
                step_id=f"retry_{original_step_id}_{retry_count}",
                kind="search",
                tool_name=tool_result.tool_name,
                query=query,
                status="success" if tool_result.status == "success" else "failed",
                result_count=len(results),
                results=[to_search_hit(result) for result in results],
                sources=format_sources(results) if results else [],
                error=tool_result.error,
                reason=f"补搜缺失证据：{original_step_id}",
                metadata=tool_result.metadata,
            )
            retry_results.append(step_result)
            search_results.extend(results)
            attempted_queries.append(query)
            state["trace"].append(
                AgentTraceStep(
                    node_name="retry_search",
                    step_type="retry" if step_result.status == "success" else "error",
                    step_id=step_result.step_id,
                    tool_name=step_result.tool_name,
                    query=query,
                    result_count=step_result.result_count,
                    reason=step_result.reason or step_result.error,
                    metadata=step_result.metadata,
                )
            )

        state["retry_count"] = retry_count
        state["retry_step_results"] = retry_results
        state["search_results"] = search_results
        state["used_retrieval"] = bool(search_results)
        state["sources"] = format_sources(search_results) if search_results else []
        state["attempted_queries"] = attempted_queries
        return state

    def _build_context_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("build_context")
        request = state["request"]
        builder = self.context_builder or ContextBuilder(
            max_chunks=request.context_max_chunks,
            token_budget=request.context_token_budget,
        )
        context_bundle = builder.build(
            question=request.question,
            plan=state["plan"],
            step_results=state.get("step_results", []),
            retry_step_results=state.get("retry_step_results", []),
            evidence_check=state.get("evidence_check") or _empty_evidence_check(),
            memory_snapshot=state.get("memory_snapshot")
            or _empty_memory_snapshot(state["conversation_id"], request.memory_window),
            permission_report=state.get("permission_report"),
        )
        state["context_bundle"] = context_bundle
        state["trace"].append(
            AgentTraceStep(
                node_name="build_context",
                step_type="context",
                result_count=len(context_bundle.included_chunks),
                reason=context_bundle.context_summary,
                metadata={
                    "included_chunks": len(context_bundle.included_chunks),
                    "excluded_chunks": len(context_bundle.excluded_chunks),
                    "token_budget": context_bundle.token_budget,
                },
            )
        )
        return state

    def _synthesize_answer_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("synthesize_answer")
        chat_client = self._chat_client()
        context_bundle = state.get("context_bundle") or _empty_context_bundle(state["request"])
        answer, stream_metrics = _generate_answer(
            chat_client,
            context_bundle.messages,
            run_id=state["run_id"],
            event_sink=_ACTIVE_EVENT_SINK.get(),
        )
        if not answer:
            if state.get("used_retrieval"):
                answer = _fallback_answer(state["search_results"])
            else:
                answer = _direct_non_retrieval_answer(state.get("step_results", []))
        state["answer"] = answer
        state["answer_stream"] = stream_metrics.model_copy(
            update={"visible_character_count": len(answer)}
        )
        state["trace"].append(
            AgentTraceStep(
                node_name="synthesize_answer",
                step_type="synthesize",
                result_count=len(state.get("search_results", [])),
                reason=(
                    "基于检索证据综合生成最终答案。"
                    if state.get("used_retrieval")
                    else "未执行检索，交由通用 Answer LLM 回答 no_search/clarify 请求。"
                ),
                metadata={"answer_stream": state["answer_stream"].model_dump()},
            )
        )
        _mark_synthesize_steps_success(state["step_results"])
        return state

    def _save_memory_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("save_memory")
        try:
            memory_write = self.memory_store.append_turn(
                conversation_id=state["conversation_id"],
                user_message=state["request"].question,
                assistant_message=state.get("answer", ""),
                sources=list(state.get("sources", [])),
                tool_calls=_tool_call_records(
                    [*state.get("step_results", []), *state.get("retry_step_results", [])]
                ),
            )
            step_type = "memory_write"
            reason = "已保存本轮原始问答、sources 和 tool calls。"
        except Exception as exc:
            memory_write = MemoryWriteResult(
                conversation_id=state["conversation_id"],
                saved=False,
                reason=str(exc),
            )
            step_type = "error"
            reason = "保存 conversation memory 失败。"

        state["memory_write"] = memory_write
        state["trace"].append(
            AgentTraceStep(
                node_name="save_memory",
                step_type=step_type,
                reason=reason,
                metadata={
                    "conversation_id": state["conversation_id"],
                    "turn_id": memory_write.turn_id,
                    "saved": memory_write.saved,
                },
            )
        )
        return state

    def _execute_search_step(
        self,
        step: PlanStep,
        request: AgentAskRequest,
        retrieval_scope: RetrievalScope | None = None,
    ) -> StepResult:
        query = step.query or request.question
        tool_result = self.tool_registry.run(
            "search_notes",
            query=query,
            top_k=request.top_k,
            mode=request.mode,
            filters=request.filters,
            **_retrieval_scope_kwargs(retrieval_scope, request.collection),
        )
        results = list(tool_result.results)
        status = "success" if tool_result.status == "success" else "failed"
        return StepResult(
            step_id=step.id,
            kind=step.kind,
            tool_name=tool_result.tool_name,
            query=query,
            status=status,
            result_count=len(results),
            results=[to_search_hit(result) for result in results],
            sources=format_sources(results) if results else [],
            error=tool_result.error,
            reason=step.reason,
            metadata=tool_result.metadata,
        )

    def _planner_service(self) -> PlannerService:
        if self.planner_service is None:
            self.planner_service = PlannerService(chat_client_factory=self._chat_client)
        return self.planner_service

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def _copy_state(state: AgentState) -> AgentState:
    copied = dict(state)
    copied["step_results"] = list(state.get("step_results", []))
    copied["retry_step_results"] = list(state.get("retry_step_results", []))
    copied["search_results"] = list(state.get("search_results", []))
    copied["sources"] = list(state.get("sources", []))
    copied["attempted_queries"] = list(state.get("attempted_queries", []))
    copied["graph_path"] = list(state.get("graph_path", []))
    copied["trace"] = list(state.get("trace", []))
    copied["node_timings"] = list(state.get("node_timings", []))
    copied["tool_catalog"] = list(state.get("tool_catalog", []))
    copied["skill_candidates"] = list(state.get("skill_candidates", []))
    return copied


def _model_data(value):
    return value.model_dump(mode="python") if hasattr(value, "model_dump") else value


def _collection_kwargs(collection: str | None) -> dict[str, str]:
    return {"collection": collection} if collection is not None else {}


def _retrieval_scope_kwargs(
    scope: RetrievalScope | None,
    explicit_collection: str | None,
) -> dict[str, Any]:
    if scope and len(scope.selected_collections) > 1:
        return {"collections": list(scope.selected_collections)}
    if scope and len(scope.selected_collections) == 1:
        return {"collection": scope.selected_collections[0]}
    if scope is not None:
        return {"collections": []}
    return _collection_kwargs(explicit_collection)


def _response_collection_name(
    retrieval_service,
    explicit_collection: str | None,
    scope: RetrievalScope | None,
) -> str:
    if scope and scope.selected_collections:
        return ",".join(scope.selected_collections)
    if scope is not None:
        return "none"
    return _effective_collection_name(retrieval_service, explicit_collection)


def _effective_collection_name(retrieval_service, collection: str | None) -> str:
    resolver = getattr(retrieval_service, "collection_name", None)
    if callable(resolver):
        return str(resolver(collection))
    config = getattr(retrieval_service, "config", None)
    return collection or str(getattr(config, "collection_name", "obsidian_notes"))


def _emit_progress_event(
    event_sink: EventSink | None,
    *,
    node_name: str,
    status: Literal["running", "completed", "failed"],
    state: AgentState,
    retrieval_service,
    metadata: dict[str, Any] | None = None,
) -> None:
    phase = _NODE_PROGRESS_PHASE.get(node_name)
    if phase is None:
        return
    request = state.get("request")
    collection = None
    result_count = None
    if phase == "retrieval" and request is not None:
        collection = _response_collection_name(
            retrieval_service,
            request.collection,
            state.get("retrieval_scope"),
        )
        if status == "completed":
            result_count = sum(
                item.result_count
                for item in [*state.get("step_results", []), *state.get("retry_step_results", [])]
            )
            rerank_metadata = next(
                (
                    value
                    for item in [*state.get("step_results", []), *state.get("retry_step_results", [])]
                    if (value := _rerank_metadata_from_step_result(item))
                ),
                {},
            )
            metadata = {**(metadata or {}), **rerank_metadata}
    progress = AgentProgressEvent(
        phase=phase,
        status=status,
        collection=collection,
        result_count=result_count,
        metadata=metadata or {},
    )
    _emit_agent_event(event_sink, "progress", progress.model_dump(mode="json"))


def _rerank_metadata_from_step_result(step_result: StepResult) -> dict[str, Any]:
    if not step_result.results:
        return {}
    run = step_result.results[0].metadata.get("rerank_run")
    return {"rerank": run} if isinstance(run, dict) else {}


def _emit_agent_event(
    event_sink: Callable[[str, dict[str, Any]], None] | None,
    name: str,
    payload: dict[str, Any],
) -> None:
    if event_sink is None:
        return
    try:
        event_sink(name, payload)
    except Exception:
        # 可观测事件不能改变 Agent 主流程；断开的 SSE 客户端不应导致 Agent 失败。
        return


def _generate_answer(
    chat_client,
    messages: list[dict[str, str]],
    *,
    run_id: str,
    event_sink: EventSink | None,
) -> tuple[str, AnswerStreamMetrics]:
    if chat_client is None:
        return "", AnswerStreamMetrics(mode="complete")

    started = perf_counter()
    stream = getattr(chat_client, "stream", None)
    if event_sink is None or not callable(stream):
        answer = chat_client.complete(messages).strip()
        return answer, AnswerStreamMetrics(
            mode="complete",
            llm_generation_ms=max(0, round((perf_counter() - started) * 1000)),
            visible_character_count=len(answer),
        )

    message_id = f"msg_{run_id}"
    chunks: list[str] = []
    reasoning_character_count = 0
    first_chunk_at: float | None = None
    first_reasoning_at: float | None = None
    answer_sequence = 0
    reasoning_sequence = 0
    try:
        for chunk in stream(messages):
            reasoning_text, content_text = _stream_chunk_parts(chunk)
            if reasoning_text:
                reasoning_sequence += 1
                reasoning_character_count += len(reasoning_text)
                if first_reasoning_at is None:
                    first_reasoning_at = perf_counter()
                _emit_agent_event(
                    event_sink,
                    "reasoning_delta",
                    {
                        "message_id": message_id,
                        "sequence": reasoning_sequence,
                        "delta": reasoning_text,
                        "node_name": "synthesize_answer",
                    },
                )
            if content_text:
                answer_sequence += 1
                if first_chunk_at is None:
                    first_chunk_at = perf_counter()
                chunks.append(content_text)
                _emit_agent_event(
                    event_sink,
                    "answer_delta",
                    {
                        "message_id": message_id,
                        "sequence": answer_sequence,
                        "delta": content_text,
                        "node_name": "synthesize_answer",
                    },
                )
    except Exception:
        if chunks:
            raise
        answer = chat_client.complete(messages).strip()
        return answer, AnswerStreamMetrics(
            mode="fallback",
            message_id=message_id,
            llm_reasoning_ttft_ms=(
                max(0, round((first_reasoning_at - started) * 1000)) if first_reasoning_at else None
            ),
            llm_generation_ms=max(0, round((perf_counter() - started) * 1000)),
            visible_character_count=len(answer),
            reasoning_character_count=reasoning_character_count,
        )

    if not chunks:
        answer = chat_client.complete(messages).strip()
        return answer, AnswerStreamMetrics(
            mode="fallback",
            message_id=message_id,
            llm_reasoning_ttft_ms=(
                max(0, round((first_reasoning_at - started) * 1000)) if first_reasoning_at else None
            ),
            llm_generation_ms=max(0, round((perf_counter() - started) * 1000)),
            visible_character_count=len(answer),
            reasoning_character_count=reasoning_character_count,
        )

    answer = "".join(chunks).strip()
    return answer, AnswerStreamMetrics(
        mode="stream",
        message_id=message_id,
        llm_ttft_ms=(max(0, round((first_chunk_at - started) * 1000)) if first_chunk_at else None),
        llm_reasoning_ttft_ms=(
            max(0, round((first_reasoning_at - started) * 1000)) if first_reasoning_at else None
        ),
        llm_generation_ms=max(0, round((perf_counter() - started) * 1000)),
        visible_character_count=len(answer),
        reasoning_character_count=reasoning_character_count,
    )


def _stream_chunk_parts(chunk: Any) -> tuple[str, str]:
    if isinstance(chunk, ChatStreamDelta):
        if chunk.kind == "reasoning":
            return chunk.text, ""
        return "", chunk.text
    if isinstance(chunk, str):
        return "", chunk
    return "", str(chunk or "")
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _non_search_step_result(step: PlanStep) -> StepResult:
    tool_name = step.kind
    status = "skipped" if step.kind in {"no_search", "clarify"} else "skipped"
    return StepResult(
        step_id=step.id,
        kind=step.kind,
        tool_name=tool_name,
        instruction=step.instruction,
        status=status,
        reason=step.reason or step.instruction,
    )


def _permission_decision_for_step(
    report: PermissionReport | None,
    step_id: str,
) -> PermissionDecision | None:
    if report is None:
        return None
    return next((item for item in report.decisions if item.step_id == step_id), None)


def _permission_blocked_step_result(
    step: PlanStep,
    report: PermissionReport | None,
) -> StepResult | None:
    decision = _permission_decision_for_step(report, step.id)
    if decision is None or decision.decision == "allow":
        return None
    status = "skipped" if decision.decision == "confirm" else "failed"
    return StepResult(
        step_id=step.id,
        kind=step.kind,
        tool_name=decision.tool_name or step.tool_name or ("search_notes" if step.kind == "search" else step.kind),
        query=step.query,
        arguments=step.arguments,
        instruction=step.instruction,
        status=status,
        error=decision.reason,
        reason=f"Permission Policy 返回 {decision.decision}，未执行该步骤。",
        metadata={"permission": decision.model_dump()},
    )


def _search_results_from_step_result(result: StepResult) -> list[SearchResult]:
    search_results: list[SearchResult] = []
    for hit in result.results:
        search_results.append(
            SearchResult(
                chunk=_text_chunk_from_hit(hit),
                score=hit.score,
            )
        )
    return search_results


def _text_chunk_from_hit(hit):
    from obsidian_rag.schema import TextChunk

    return TextChunk(text=hit.text or hit.text_preview, metadata=hit.metadata)


def _fallback_answer(results: list[SearchLikeResult]) -> str:
    preview = " ".join(results[0].chunk.text.split())[:240]
    return f"已执行计划并找到本地资料，但模型没有生成最终答案。证据摘要：{preview}"


def _direct_non_retrieval_answer(step_results: list[StepResult]) -> str:
    for result in step_results:
        if result.instruction:
            return result.instruction
        if result.reason:
            return result.reason
    return "当前计划没有需要查询本地知识库的步骤。"


def _mark_synthesize_steps_success(step_results: list[StepResult]) -> None:
    for index, result in enumerate(step_results):
        if result.kind == "synthesize":
            step_results[index] = result.model_copy(update={"status": "success", "tool_name": "synthesize"})


def _check_evidence(
    step_results: list[StepResult],
    retry_step_results: list[StepResult],
    retry_count: int,
    attempted_queries: list[str],
) -> EvidenceCheckResult:
    search_steps = [result for result in step_results if result.kind == "search"]
    checked_step_ids = [result.step_id for result in search_steps]
    if not search_steps:
        return EvidenceCheckResult(
            is_sufficient=True,
            checked_step_ids=[],
            retry_count=retry_count,
            reason="计划里没有 search step，不需要证据检查。",
        )

    missing_steps = [result for result in search_steps if not _step_has_evidence(result, retry_step_results)]
    if not missing_steps:
        return EvidenceCheckResult(
            is_sufficient=True,
            checked_step_ids=checked_step_ids,
            retry_count=retry_count,
            reason="所有 search step 都有检索结果。",
        )

    missing_points = [f"{result.step_id} 没有检索到证据：{result.query or result.instruction or result.kind}" for result in missing_steps]
    suggested_queries = [
        query for query in (_suggest_retry_query(result.query) for result in missing_steps) if query and query not in attempted_queries
    ]
    return EvidenceCheckResult(
        is_sufficient=False,
        missing_points=missing_points,
        suggested_queries=suggested_queries,
        checked_step_ids=checked_step_ids,
        missing_step_ids=[result.step_id for result in missing_steps],
        retry_count=retry_count,
        reason="部分 search step 没有证据，需要补搜。" if suggested_queries else "部分 search step 没有证据，且没有新的补搜 query。",
    )


def _step_has_evidence(step_result: StepResult, retry_step_results: list[StepResult]) -> bool:
    if step_result.result_count > 0:
        return True
    prefix = f"retry_{step_result.step_id}_"
    return any(result.step_id.startswith(prefix) and result.result_count > 0 for result in retry_step_results)


def _suggest_retry_query(query: str | None) -> str | None:
    if not query:
        return None
    query = query.strip()
    if not query:
        return None
    if "食品安全" in query:
        return query
    return f"{query} 食品安全"


def _route_after_evidence_check(state: AgentState) -> str:
    evidence_check = state.get("evidence_check")
    request = state["request"]
    retryable_missing_steps = [
        step_id
        for step_id in evidence_check.missing_step_ids
        if (
            (decision := _permission_decision_for_step(state.get("permission_report"), step_id)) is None
            or decision.decision == "allow"
        )
    ] if evidence_check else []
    if (
        evidence_check
        and not evidence_check.is_sufficient
        and evidence_check.suggested_queries
        and retryable_missing_steps
        and state.get("retry_count", 0) < request.max_retries
    ):
        return "retry_search"
    return "build_context"


def _empty_evidence_check() -> EvidenceCheckResult:
    return EvidenceCheckResult(is_sufficient=False, reason="没有执行 evidence check。")


def _empty_context_bundle(request: AgentAskRequest) -> ContextBundle:
    return ContextBundle(
        messages=[
            {"role": "system", "content": "你是 Obsidian 本地知识库 RAG 的答案综合器。"},
            {"role": "user", "content": request.question},
        ],
        token_budget=request.context_token_budget,
        context_summary="没有构建 ContextBundle。",
    )


def _empty_memory_snapshot(conversation_id: str, window: int) -> MemorySnapshot:
    return MemorySnapshot(conversation_id=conversation_id, window=window)


def _empty_memory_compaction(conversation_id: str) -> MemoryCompactionResult:
    return MemoryCompactionResult(conversation_id=conversation_id, reason="没有执行 Memory Compaction。")


def _tool_call_records(step_results: list[StepResult]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for result in step_results:
        if not result.tool_name:
            continue
        records.append(
            {
                "step_id": result.step_id,
                "tool": result.tool_name,
                "query": result.query,
                "arguments": result.arguments,
                "status": result.status,
                "result_count": result.result_count,
            }
        )
    return records
