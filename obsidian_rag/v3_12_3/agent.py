from __future__ import annotations

import json
from typing import Any

from obsidian_rag.core.agent.service import (
    AgentService as CoreAgentService,
    AgentState,
    _ACTIVE_EVENT_SINK,
    _copy_state,
    _emit_agent_event,
    _empty_memory_snapshot,
    _non_search_step_result,
    _rerank_metadata_from_step_result,
    _search_results_from_step_result,
)
from obsidian_rag.core.context import build_memory_aware_planner_question
from obsidian_rag.core.schemas import (
    AgentTraceStep,
    EvidenceCheckResult,
    PlanRequest,
    PlanStep,
    PlannerToolDefinition,
    StepResult,
    ToolObservation,
)


class McpAgentService(CoreAgentService):
    """在公共 Agent Core 上增加 Planner MCP Tool Selection 与统一执行。"""

    def __init__(self, *args, planner_tools: list[PlannerToolDefinition], **kwargs):
        self.planner_tools = planner_tools
        super().__init__(*args, **kwargs)

    def _initial_state(self, request) -> AgentState:
        state = super()._initial_state(request)
        state["tool_catalog"] = self._catalog_for_request(request)
        return state

    def _planner_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        request = state["request"]
        state["graph_path"].append("planner")
        catalog = self._catalog_for_request(request)
        state["tool_catalog"] = catalog
        planner_question = build_memory_aware_planner_question(
            request.question,
            state.get("memory_snapshot")
            or _empty_memory_snapshot(state["conversation_id"], request.memory_window),
        )
        planner_response = self._planner_service().plan(
            PlanRequest(
                question=planner_question,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
                max_steps=request.max_steps,
                tools=catalog,
            )
        )
        state["plan"] = planner_response.plan
        state["trace"].append(
            AgentTraceStep(
                node_name="planner",
                step_type="planner",
                reason="Planner 根据本地检索能力和 MCP Tool Catalog 生成计划。",
                metadata={
                    "planner_graph_path": planner_response.graph_path,
                    "step_count": len(planner_response.plan.steps),
                    "tool_catalog": [tool.name for tool in catalog],
                },
            )
        )
        return state

    def _execute_steps_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("execute_steps")
        request = state["request"]
        step_results: list[StepResult] = []
        search_results = []

        for step in state["plan"].steps:
            if step.kind == "search":
                result = self._execute_search_step(step, request)
                search_results.extend(_search_results_from_step_result(result))
            elif step.kind == "tool":
                result = self._execute_tool_step(step)
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
                    metadata={
                        **_rerank_metadata_from_step_result(result),
                        "argument_names": sorted(result.arguments),
                        "observation_source": result.observation.source if result.observation else None,
                        "tool_metadata": result.observation.metadata if result.observation else {},
                    },
                )
            )

        state["step_results"] = step_results
        state["search_results"] = search_results
        state["used_retrieval"] = bool(search_results)
        from obsidian_rag.prompting import format_sources

        state["sources"] = format_sources(search_results) if search_results else []
        return state

    def _execute_tool_step(self, step: PlanStep) -> StepResult:
        tool_name = step.tool_name or ""
        definition = next((item for item in self.tool_registry.list_tools() if item.name == tool_name), None)
        _emit_agent_event(
            _ACTIVE_EVENT_SINK.get(),
            "tool_started",
            {
                "step_id": step.id,
                "tool_name": tool_name,
                "source": definition.source if definition else "unknown",
                "argument_names": sorted(step.arguments),
            },
        )
        result = self.tool_registry.run(tool_name, **step.arguments)
        status = "success" if result.status == "success" else "failed"
        summary = _observation_summary(result.data, result.error)
        observation = ToolObservation(
            step_id=step.id,
            tool_name=result.tool_name,
            source=definition.source if definition else str(result.metadata.get("source") or "unknown"),
            status=status,
            data=result.data,
            summary=summary,
            metadata=result.metadata,
            error=result.error,
        )
        _emit_agent_event(
            _ACTIVE_EVENT_SINK.get(),
            "tool_finished",
            {
                "step_id": step.id,
                "tool_name": result.tool_name,
                "source": observation.source,
                "status": status,
                "result_count": 1 if status == "success" else 0,
                "duration_ms": result.metadata.get("duration_ms"),
                "error": result.error,
            },
        )
        return StepResult(
            step_id=step.id,
            kind="tool",
            tool_name=result.tool_name,
            arguments=step.arguments,
            instruction=summary,
            status=status,
            result_count=1 if status == "success" else 0,
            error=result.error,
            reason=step.reason,
            observation=observation,
        )

    def _evidence_check_node(self, state: AgentState) -> AgentState:
        state = super()._evidence_check_node(state)
        failed_tools = [
            item for item in state.get("step_results", [])
            if item.kind == "tool" and item.status == "failed"
        ]
        if not failed_tools:
            return state
        current = state["evidence_check"]
        state["evidence_check"] = EvidenceCheckResult(
            is_sufficient=False,
            missing_points=[
                *current.missing_points,
                *(f"{item.step_id} 工具执行失败：{item.error or item.tool_name}" for item in failed_tools),
            ],
            suggested_queries=current.suggested_queries,
            checked_step_ids=[*current.checked_step_ids, *(item.step_id for item in failed_tools)],
            missing_step_ids=[*current.missing_step_ids, *(item.step_id for item in failed_tools)],
            retry_count=current.retry_count,
            reason="知识库证据检查完成，但部分 MCP Tool Observation 缺失。",
        )
        if state.get("trace"):
            state["trace"][-1] = state["trace"][-1].model_copy(
                update={
                    "reason": state["evidence_check"].reason,
                    "metadata": {
                        **state["trace"][-1].metadata,
                        "is_sufficient": False,
                        "failed_tool_step_ids": [item.step_id for item in failed_tools],
                        "missing_step_ids": state["evidence_check"].missing_step_ids,
                    },
                }
            )
        return state

    def _synthesize_answer_node(self, state: AgentState) -> AgentState:
        state = super()._synthesize_answer_node(state)
        observations = [item.observation for item in state.get("step_results", []) if item.observation]
        if observations and state.get("trace"):
            state["trace"][-1] = state["trace"][-1].model_copy(
                update={
                    "reason": "综合知识库 chunks 与 Tool Observations 生成最终答案。",
                    "metadata": {
                        **state["trace"][-1].metadata,
                        "tool_observation_count": len(observations),
                    },
                }
            )
        return state

    def _catalog_for_request(self, request) -> list[PlannerToolDefinition]:
        if not getattr(request, "mcp_enabled", True):
            return []
        selected = getattr(request, "mcp_tool_names", None)
        if not selected:
            return list(self.planner_tools)
        allowed = set(selected)
        return [tool for tool in self.planner_tools if tool.name in allowed]


def _observation_summary(data: Any, error: str | None) -> str:
    if error:
        return f"工具调用失败：{error}"
    try:
        text = json.dumps(data, ensure_ascii=False, default=str)
    except TypeError:
        text = str(data)
    return text if len(text) <= 600 else f"{text[:600]}..."
