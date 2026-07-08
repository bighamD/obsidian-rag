from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from obsidian_rag.llm import ToolCall
from obsidian_rag.prompting import format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3_2.tools import AGENT_TOOLS, TOOL_CALLING_SYSTEM_PROMPT
from obsidian_rag.v3_3.schemas import AgentAskRequest, AgentAskResponse, AgentTraceStep


class AgentState(TypedDict, total=False):
    request: AgentAskRequest
    question: str
    messages: list[dict]
    tool_call: ToolCall | None
    tool_calls: list[ToolCall]
    results: list[SearchResult]
    answer: str
    used_retrieval: bool
    sources: list[str]
    graph_path: list[str]
    trace: list[AgentTraceStep]
    has_evidence: bool


class AgentService:
    def __init__(self, retrieval_service, chat_client=None, chat_client_factory=None):
        self.retrieval_service = retrieval_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory
        self.graph = self._build_graph()

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        initial_state: AgentState = {
            "request": request,
            "question": request.question,
            "messages": [
                {"role": "system", "content": TOOL_CALLING_SYSTEM_PROMPT},
                {"role": "user", "content": request.question},
            ],
            "tool_calls": [],
            "results": [],
            "answer": "",
            "used_retrieval": False,
            "sources": [],
            "graph_path": [],
            "trace": [],
            "has_evidence": False,
        }
        final_state = self.graph.invoke(initial_state)
        return AgentAskResponse(
            question=request.question,
            answer=final_state.get("answer") or "图执行结束，但没有生成答案。",
            used_retrieval=bool(final_state.get("used_retrieval", False)),
            sources=final_state.get("sources", []),
            tool_calls=final_state.get("tool_calls", []),
            graph_path=final_state.get("graph_path", []),
            trace=final_state.get("trace", []),
        )

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("select_tool", self._select_tool_node)
        graph.add_node("search_notes", self._search_notes_node)
        graph.add_node("no_search", self._no_search_node)
        graph.add_node("clarify", self._clarify_node)
        graph.add_node("evidence_check", self._evidence_check_node)
        graph.add_node("answer", self._answer_node)

        graph.add_edge(START, "select_tool")
        graph.add_conditional_edges(
            "select_tool",
            _route_after_tool_selection,
            {
                "search_notes": "search_notes",
                "no_search": "no_search",
                "clarify": "clarify",
                "answer": "answer",
            },
        )
        graph.add_edge("search_notes", "evidence_check")
        graph.add_edge("evidence_check", "answer")
        graph.add_edge("answer", END)
        graph.add_edge("no_search", END)
        graph.add_edge("clarify", END)
        return graph.compile()

    def _select_tool_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("select_tool")
        chat_client = self._chat_client()
        if chat_client is None:
            state["answer"] = "没有配置支持 Tool Calling 的 LLM 客户端。"
            state["trace"].append(
                AgentTraceStep(
                    node_name="select_tool",
                    step_type="answer",
                    reason="没有配置支持 Tool Calling 的 LLM 客户端。",
                )
            )
            return state

        tool_response = chat_client.complete_with_tools(state["messages"], AGENT_TOOLS)
        if not tool_response.tool_calls:
            state["answer"] = tool_response.content or "模型没有选择任何工具，无法继续执行。"
            state["trace"].append(
                AgentTraceStep(node_name="select_tool", step_type="answer", reason="模型没有返回 tool_calls。")
            )
            return state

        tool_call = tool_response.tool_calls[0]
        state["tool_call"] = tool_call
        state["tool_calls"] = [tool_call]
        state["trace"].append(
            AgentTraceStep(
                node_name="select_tool",
                step_type="tool_selection",
                tool_name=tool_call.name,
                query=str(tool_call.arguments.get("query", "")) or None,
                reason=str(tool_call.arguments.get("reason", "")) or None,
                metadata={"arguments": tool_call.arguments, "content": tool_response.content},
            )
        )
        state["messages"].append(_assistant_tool_call_message(tool_response.content, tool_call))
        return state

    def _search_notes_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("search_notes")
        request = state["request"]
        tool_call = state.get("tool_call")
        query = request.question if tool_call is None else str(tool_call.arguments.get("query") or request.question)
        top_k = request.top_k if tool_call is None else _tool_top_k(tool_call, default=request.top_k)
        raw_results = self.retrieval_service.search(query, top_k=top_k, mode=request.mode, filters=request.filters)
        results = [_as_search_result(result) for result in raw_results]
        state["results"] = results
        state["used_retrieval"] = True
        state["trace"].append(
            AgentTraceStep(
                node_name="search_notes",
                step_type="tool_result",
                tool_name="search_notes",
                query=query,
                result_count=len(results),
                results=[to_search_hit(result) for result in results],
            )
        )
        if tool_call is not None:
            state["messages"].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _tool_result_content(results),
                }
            )
        return state

    def _evidence_check_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("evidence_check")
        results = state.get("results", [])
        state["has_evidence"] = bool(results)
        state["trace"].append(
            AgentTraceStep(
                node_name="evidence_check",
                step_type="evidence_check",
                reason="找到可用于回答的本地资料。" if results else "没有找到足够相关的本地资料。",
                result_count=len(results),
            )
        )
        return state

    def _answer_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("answer")
        results = state.get("results", [])
        if not results:
            if not state.get("answer"):
                state["answer"] = "本地知识库没有足够相关资料来回答这个问题。"
            state["trace"].append(AgentTraceStep(node_name="answer", step_type="answer", reason="证据不足或无工具结果。"))
            return state

        chat_client = self._chat_client()
        answer = "" if chat_client is None else chat_client.complete(state["messages"]).strip()
        if not answer:
            answer = _fallback_evidence_answer(results)
        state["answer"] = answer
        state["sources"] = format_sources(results)
        state["trace"].append(AgentTraceStep(node_name="answer", step_type="answer", reason="模型读取 tool result 后生成最终答案。"))
        return state

    def _no_search_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("no_search")
        tool_call = state.get("tool_call")
        arguments = tool_call.arguments if tool_call else {}
        state["answer"] = str(arguments.get("answer") or arguments.get("reason") or "这个问题不适合查询本地知识库。")
        state["used_retrieval"] = False
        state["trace"].append(AgentTraceStep(node_name="no_search", step_type="answer", reason="no_search 节点直接返回。"))
        return state

    def _clarify_node(self, state: AgentState) -> AgentState:
        state = _copy_state(state)
        state["graph_path"].append("clarify")
        tool_call = state.get("tool_call")
        arguments = tool_call.arguments if tool_call else {}
        state["answer"] = str(arguments.get("question") or "可以补充一下你想查询的范围吗？")
        state["used_retrieval"] = False
        state["trace"].append(AgentTraceStep(node_name="clarify", step_type="answer", reason="clarify 节点向用户追问。"))
        return state

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def _route_after_tool_selection(state: AgentState) -> str:
    tool_call = state.get("tool_call")
    if state.get("answer") and tool_call is None:
        return "answer"
    if tool_call is None:
        return "answer"
    if tool_call.name in {"search_notes", "no_search", "clarify"}:
        return tool_call.name
    return "answer"


def _copy_state(state: AgentState) -> AgentState:
    copied = dict(state)
    copied["messages"] = list(state.get("messages", []))
    copied["tool_calls"] = list(state.get("tool_calls", []))
    copied["results"] = list(state.get("results", []))
    copied["sources"] = list(state.get("sources", []))
    copied["graph_path"] = list(state.get("graph_path", []))
    copied["trace"] = list(state.get("trace", []))
    return copied


def _tool_top_k(tool_call: ToolCall, default: int) -> int:
    raw = tool_call.arguments.get("top_k", default)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, 20))


def _assistant_tool_call_message(content: str | None, tool_call: ToolCall) -> dict:
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
        ],
    }


def _tool_result_content(results: list[SearchResult]) -> str:
    payload: list[dict[str, Any]] = []
    for result in results:
        metadata = result.chunk.metadata
        payload.append(
            {
                "source": metadata.get("source", "unknown"),
                "chunk_id": metadata.get("chunk_id"),
                "topic": metadata.get("topic"),
                "score": result.score,
                "text": result.chunk.text,
            }
        )
    return json.dumps(payload, ensure_ascii=False)


def _fallback_evidence_answer(results: list[SearchResult]) -> str:
    preview = " ".join(results[0].chunk.text.split())[:240]
    return f"已找到本地资料，但模型没有生成最终答案。证据摘要：{preview}"


def _as_search_result(result: SearchResult | RankedSearchResult) -> SearchResult:
    if isinstance(result, SearchResult):
        return result
    return SearchResult(chunk=result.chunk, score=result.score)

