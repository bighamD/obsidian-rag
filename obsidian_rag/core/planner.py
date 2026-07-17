from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from obsidian_rag.core.schemas import Plan, PlanRequest, PlanResponse, PlanStep, PlannerTraceStep


PLANNER_SYSTEM_PROMPT = """你是 Obsidian 本地知识库 RAG 的 Planner。

你的任务是把用户问题拆成一个可执行计划，只输出 JSON，不要输出 Markdown，不要直接回答用户。

Planner 只负责规划，不执行检索、不生成最终答案。

可选 step.kind：
- search：需要查询本地知识库。必须提供 query。
- tool：必须从 user payload 的 tools 中选择一个工具，提供 tool_name 和符合 input_schema 的 arguments。
- synthesize：综合前面步骤结果。必须提供 instruction，可用 depends_on 表示依赖步骤。
- no_search：问题明显依赖实时外部信息、闲聊或不适合本地知识库。必须提供 instruction。
- clarify：问题太短、指代不明或范围不清。必须提供 instruction。

JSON 格式：
{
  "goal": "一句话描述计划目标",
  "steps": [
    {
      "id": "s1",
      "kind": "search | tool | synthesize | no_search | clarify",
      "query": "当 kind=search 时提供检索词，否则为 null",
      "tool_name": "当 kind=tool 时必须来自 tools[].name，否则为 null",
      "arguments": {"当 kind=tool 时": "根据 input_schema 构造参数"},
      "instruction": "非 search 步骤的执行说明，search 可为 null",
      "depends_on": ["s1"],
      "reason": "一句话说明为什么需要这一步"
    }
  ]
}

规划要求：
- 简单知识库问题：1 个 search step + 1 个 synthesize step。
- 多主题知识库问题：每个主题一个 search step，最后一个 synthesize step。
- tools 非空且某个工具明确能提供所需外部事实时，生成 tool step；不得编造工具名或参数。
- tools 为空或没有合适工具时，实时天气、股价、新闻等问题返回 1 个 no_search step。
- 一个问题同时需要知识库和外部工具时，可以组合 search + tool + synthesize。
- 指代不明的问题：返回 1 个 clarify step。
- steps 数量不要超过用户给出的 max_steps。
"""


class PlannerState(TypedDict, total=False):
    request: PlanRequest
    messages: list[dict[str, str]]
    raw_output: str
    plan: Plan
    graph_path: list[str]
    trace: list[PlannerTraceStep]
    error_reason: str
    error_metadata: dict[str, Any]


class PlannerService:
    def __init__(self, chat_client=None, chat_client_factory=None):
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory
        self.graph = self._build_graph()

    def plan(self, request: PlanRequest) -> PlanResponse:
        initial_state: PlannerState = {
            "request": request,
            "messages": [],
            "graph_path": [],
            "trace": [],
        }
        final_state = self.graph.invoke(initial_state)
        return PlanResponse(
            question=request.question,
            plan=final_state.get("plan") or _clarify_plan("Planner graph 没有生成计划。"),
            graph_path=final_state.get("graph_path", []),
            trace=final_state.get("trace", []),
        )

    def _build_graph(self):
        graph = StateGraph(PlannerState)
        graph.add_node("build_prompt", self._build_prompt_node)
        graph.add_node("call_planner", self._call_planner_node)
        graph.add_node("parse_plan", self._parse_plan_node)

        graph.add_edge(START, "build_prompt")
        graph.add_edge("build_prompt", "call_planner")
        graph.add_edge("call_planner", "parse_plan")
        graph.add_edge("parse_plan", END)
        return graph.compile()

    def _build_prompt_node(self, state: PlannerState) -> PlannerState:
        state = _copy_state(state)
        request = state["request"]
        state["graph_path"].append("build_prompt")
        state["messages"] = _build_planner_messages(request)
        state["trace"].append(
            PlannerTraceStep(
                node_name="build_prompt",
                step_type="planner_prompt",
                reason="已把用户问题和计划约束构造成 LLM Planner messages。",
                metadata={
                    "max_steps": request.max_steps,
                    "mode": request.mode,
                    "top_k": request.top_k,
                    "tool_count": len(request.tools),
                },
            )
        )
        return state

    def _call_planner_node(self, state: PlannerState) -> PlannerState:
        state = _copy_state(state)
        state["graph_path"].append("call_planner")
        client = self._chat_client()
        if client is None:
            return _with_planner_error(
                state,
                reason="没有配置 LLM Planner 客户端。",
                plan_reason="没有配置 LLM Planner 客户端，无法生成计划。",
            )

        try:
            state["raw_output"] = client.complete(state["messages"])
        except Exception as exc:
            return _with_planner_error(
                state,
                reason="LLM Planner 调用失败，已返回降级澄清计划。",
                plan_reason="LLM Planner 调用失败，无法生成可靠计划。",
                metadata={"error_type": type(exc).__name__, "error": str(exc)},
            )
        state["trace"].append(
            PlannerTraceStep(
                node_name="call_planner",
                step_type="planner_output",
                reason="LLM Planner 返回原始计划文本。",
                metadata={"raw_output": state["raw_output"]},
            )
        )
        return state

    def _parse_plan_node(self, state: PlannerState) -> PlannerState:
        state = _copy_state(state)
        state["graph_path"].append("parse_plan")
        request = state["request"]
        if state.get("error_reason"):
            state["plan"] = _clarify_plan(state["error_reason"])
            return state

        raw_output = state.get("raw_output", "")
        plan = parse_plan_json(raw_output, question=request.question)
        plan = _limit_steps(plan, request.max_steps)
        state["plan"] = plan
        state["trace"].append(
            PlannerTraceStep(
                node_name="parse_plan",
                step_type="planner_output",
                reason="已把 LLM 输出解析为结构化 Plan。",
                metadata={"step_count": len(plan.steps)},
            )
        )
        return state

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def _copy_state(state: PlannerState) -> PlannerState:
    copied = dict(state)
    copied["messages"] = list(state.get("messages", []))
    copied["graph_path"] = list(state.get("graph_path", []))
    copied["trace"] = list(state.get("trace", []))
    copied["error_metadata"] = dict(state.get("error_metadata", {}))
    return copied


def _with_planner_error(
    state: PlannerState,
    reason: str,
    plan_reason: str,
    metadata: dict[str, Any] | None = None,
) -> PlannerState:
    state["error_reason"] = plan_reason
    state["error_metadata"] = metadata or {}
    state["trace"] = [
        PlannerTraceStep(
            node_name="call_planner",
            step_type="planner_error",
            reason=reason,
            metadata=state["error_metadata"],
        )
    ]
    return state


def parse_plan_json(raw_output: str, question: str) -> Plan:
    try:
        payload = json.loads(_extract_json(raw_output))
        return Plan(**payload)
    except (json.JSONDecodeError, TypeError, ValidationError):
        return _clarify_plan("LLM Planner 没有返回可解析的结构化 JSON。")


def _build_planner_messages(request: PlanRequest) -> list[dict[str, str]]:
    user_payload: dict[str, Any] = {
        "question": request.question,
        "top_k": request.top_k,
        "mode": request.mode,
        "filters": request.filters.model_dump(exclude_none=True) if request.filters else None,
        "max_steps": request.max_steps,
        "tools": [tool.model_dump(mode="json") for tool in request.tools],
    }
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _extract_json(raw_output: str) -> str:
    text = raw_output.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _clarify_plan(reason: str) -> Plan:
    return Plan(
        goal="澄清用户问题",
        steps=[
            PlanStep(
                id="s1",
                kind="clarify",
                instruction="请用户补充更明确的问题范围。",
                reason=reason,
            )
        ],
    )


def _limit_steps(plan: Plan, max_steps: int) -> Plan:
    if len(plan.steps) <= max_steps:
        return plan
    return Plan(goal=plan.goal, steps=plan.steps[:max_steps])
