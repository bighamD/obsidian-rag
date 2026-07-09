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
from obsidian_rag.v3_5.schemas import AgentAskRequest, AgentAskResponse, AgentTraceStep, StepResult
from obsidian_rag.v3_5.tools import ToolRegistry, build_search_tool_registry


class AgentState(TypedDict, total=False):
    run_id: str
    request: AgentAskRequest
    plan: Plan
    step_results: list[StepResult]
    search_results: list[SearchResult]
    answer: str
    used_retrieval: bool
    sources: list[str]
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
            "search_results": [],
            "answer": "",
            "used_retrieval": False,
            "sources": [],
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
            graph_path=final_state.get("graph_path", []),
            trace=final_state.get("trace", []),
        )

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("planner", self._planner_node)
        graph.add_node("execute_steps", self._execute_steps_node)
        graph.add_node("synthesize_answer", self._synthesize_answer_node)

        graph.add_edge(START, "planner")
        graph.add_edge("planner", "execute_steps")
        graph.add_edge("execute_steps", "synthesize_answer")
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
        search_results: list[SearchResult] = []

        for step in state["plan"].steps:
            if step.kind == "search":
                result = self._execute_search_step(step, request)
                step_results.append(result)
                search_results.extend(_search_results_from_step(result))
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
        results = [_as_search_result(result) for result in tool_result.results]
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
    copied["search_results"] = list(state.get("search_results", []))
    copied["sources"] = list(state.get("sources", []))
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


def _search_results_from_step(result: StepResult) -> list[SearchResult]:
    search_results = []
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


def _fallback_answer(results: list[SearchResult]) -> str:
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


def _as_search_result(result: SearchResult | RankedSearchResult) -> SearchResult:
    if isinstance(result, SearchResult):
        return result
    return SearchResult(chunk=result.chunk, score=result.score)
