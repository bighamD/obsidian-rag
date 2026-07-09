from __future__ import annotations

import json
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from obsidian_rag.prompting import format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3_4.planner.service import PlannerService
from obsidian_rag.v3_4.schemas import Plan, PlanRequest, PlanStep
from obsidian_rag.v3_6.schemas import AgentAskRequest, AgentAskResponse, AgentTraceStep, EvidenceCheckResult, StepResult
from obsidian_rag.v3_6.tools import ToolRegistry, build_search_tool_registry


SearchLikeResult = SearchResult | RankedSearchResult


class AgentState(TypedDict, total=False):
    run_id: str
    request: AgentAskRequest
    plan: Plan
    step_results: list[StepResult]
    retry_step_results: list[StepResult]
    evidence_check: EvidenceCheckResult
    search_results: list[SearchLikeResult]
    answer: str
    used_retrieval: bool
    sources: list[str]
    retry_count: int
    attempted_queries: list[str]
    graph_path: list[str]
    trace: list[AgentTraceStep]


class AgentService:
    def __init__(
        self,
        retrieval_service,
        planner_service: PlannerService | None = None,
        chat_client=None,
        chat_client_factory=None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.planner_service = planner_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory
        self.tool_registry = tool_registry or build_search_tool_registry(retrieval_service)
        self.graph = self._build_graph()

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        initial_state: AgentState = {
            "run_id": f"run_{uuid.uuid4().hex[:12]}",
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
        }
        final_state = self.graph.invoke(initial_state)
        return AgentAskResponse(
            run_id=final_state["run_id"],
            question=request.question,
            answer=final_state.get("answer") or "执行结束，但没有生成最终答案。",
            used_retrieval=bool(final_state.get("used_retrieval", False)),
            sources=final_state.get("sources", []),
            plan=final_state["plan"],
            step_results=final_state.get("step_results", []),
            retry_step_results=final_state.get("retry_step_results", []),
            evidence_check=final_state.get("evidence_check") or _empty_evidence_check(),
            graph_path=final_state.get("graph_path", []),
            trace=final_state.get("trace", []),
        )

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("planner", self._planner_node)
        graph.add_node("execute_steps", self._execute_steps_node)
        graph.add_node("evidence_check", self._evidence_check_node)
        graph.add_node("retry_search", self._retry_search_node)
        graph.add_node("synthesize_answer", self._synthesize_answer_node)

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "execute_steps")
        graph.add_edge("execute_steps", "evidence_check")
        graph.add_conditional_edges(
            "evidence_check",
            _route_after_evidence_check,
            {"retry_search": "retry_search", "synthesize_answer": "synthesize_answer"},
        )
        graph.add_edge("retry_search", "evidence_check")
        graph.add_edge("synthesize_answer", END)
        return graph.compile()

    def _planner_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        request = state["request"]
        state["graph_path"].append("planner")
        planner = self._planner_service()
        planner_response = planner.plan(
            PlanRequest(
                question=request.question,
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
            if step.kind == "search":
                result = self._execute_search_step(step, request)
                step_results.append(result)
                search_results.extend(_search_results_from_step_result(result))
                state["trace"].append(
                    AgentTraceStep(
                        node_name="execute_steps",
                        step_type="tool_result" if result.status == "success" else "error",
                        step_id=step.id,
                        tool_name=result.tool_name,
                        query=result.query,
                        result_count=result.result_count,
                        reason=result.reason or result.error,
                    )
                )
                continue

            result = _non_search_step_result(step)
            step_results.append(result)
            state["trace"].append(
                AgentTraceStep(
                    node_name="execute_steps",
                    step_type="tool_result",
                    step_id=step.id,
                    tool_name=result.tool_name,
                    reason=result.reason,
                )
            )

        state["step_results"] = step_results
        state["search_results"] = search_results
        state["used_retrieval"] = bool(search_results)
        state["sources"] = format_sources(search_results) if search_results else []
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
            tool_result = self.tool_registry.run(
                "search_notes",
                query=query,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
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
                )
            )

        state["retry_count"] = retry_count
        state["retry_step_results"] = retry_results
        state["search_results"] = search_results
        state["used_retrieval"] = bool(search_results)
        state["sources"] = format_sources(search_results) if search_results else []
        state["attempted_queries"] = attempted_queries
        return state

    def _synthesize_answer_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("synthesize_answer")
        if not state.get("used_retrieval"):
            state["answer"] = _direct_non_retrieval_answer(state.get("step_results", []))
            state["trace"].append(
                AgentTraceStep(
                    node_name="synthesize_answer",
                    step_type="synthesize",
                    reason="没有执行检索，直接返回 no_search/clarify 计划中的说明。",
                )
            )
            return state

        chat_client = self._chat_client()
        answer = "" if chat_client is None else chat_client.complete(_build_synthesis_messages(state)).strip()
        if not answer:
            answer = _fallback_answer(state["search_results"])
        state["answer"] = answer
        state["trace"].append(
            AgentTraceStep(
                node_name="synthesize_answer",
                step_type="synthesize",
                result_count=len(state.get("search_results", [])),
                reason="综合多个 step result 生成最终答案。",
            )
        )
        _mark_synthesize_steps_success(state["step_results"])
        return state

    def _execute_search_step(self, step: PlanStep, request: AgentAskRequest) -> StepResult:
        query = step.query or request.question
        tool_result = self.tool_registry.run(
            "search_notes",
            query=query,
            top_k=request.top_k,
            mode=request.mode,
            filters=request.filters,
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
    return copied


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

    return TextChunk(text=hit.text_preview, metadata=hit.metadata)


def _build_synthesis_messages(state: AgentState) -> list[dict[str, str]]:
    payload = {
        "question": state["request"].question,
        "plan": state["plan"].model_dump(),
        "step_results": [result.model_dump() for result in state.get("step_results", [])],
    }
    return [
        {
            "role": "system",
            "content": "你是 Obsidian 本地知识库 RAG 的答案综合器。只能基于 step_results 中的证据回答，并在答案中保留来源线索。",
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


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
    if (
        evidence_check
        and not evidence_check.is_sufficient
        and evidence_check.suggested_queries
        and state.get("retry_count", 0) < request.max_retries
    ):
        return "retry_search"
    return "synthesize_answer"


def _empty_evidence_check() -> EvidenceCheckResult:
    return EvidenceCheckResult(is_sufficient=False, reason="没有执行 evidence check。")
