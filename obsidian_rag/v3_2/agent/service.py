from __future__ import annotations

import json

from obsidian_rag.llm import ToolCall
from obsidian_rag.prompting import format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3_2.schemas import AgentAskRequest, AgentAskResponse, AgentTraceStep
from obsidian_rag.v3_2.tools import AGENT_TOOLS, TOOL_CALLING_SYSTEM_PROMPT


class AgentService:
    def __init__(self, retrieval_service, chat_client=None, chat_client_factory=None):
        self.retrieval_service = retrieval_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        chat_client = self._chat_client()
        if chat_client is None:
            return _fallback_response(request.question, "没有配置支持 Tool Calling 的 LLM 客户端。")

        messages = [
            {"role": "system", "content": TOOL_CALLING_SYSTEM_PROMPT},
            {"role": "user", "content": request.question},
        ]
        tool_response = chat_client.complete_with_tools(messages, AGENT_TOOLS)
        if not tool_response.tool_calls:
            return AgentAskResponse(
                question=request.question,
                answer=tool_response.content or "模型没有选择任何工具，无法继续执行。",
                used_retrieval=False,
                sources=[],
                tool_calls=[],
                trace=[AgentTraceStep(step_type="answer", reason="模型没有返回 tool_calls。")],
            )

        tool_call = tool_response.tool_calls[0]
        trace = [
            AgentTraceStep(
                step_type="tool_selection",
                tool_name=tool_call.name,
                query=str(tool_call.arguments.get("query", "")) or None,
                reason=str(tool_call.arguments.get("reason", "")) or None,
                metadata={"arguments": tool_call.arguments},
            )
        ]

        if tool_call.name == "no_search":
            trace.append(AgentTraceStep(step_type="answer", reason="按 no_search 工具结果直接回答。"))
            return AgentAskResponse(
                question=request.question,
                answer=str(tool_call.arguments.get("answer") or tool_call.arguments.get("reason") or "这个问题不适合查询本地知识库。"),
                used_retrieval=False,
                sources=[],
                tool_calls=[tool_call],
                trace=trace,
            )

        if tool_call.name == "clarify":
            trace.append(AgentTraceStep(step_type="answer", reason="按 clarify 工具结果向用户追问。"))
            return AgentAskResponse(
                question=request.question,
                answer=str(tool_call.arguments.get("question") or "可以补充一下你想查询的范围吗？"),
                used_retrieval=False,
                sources=[],
                tool_calls=[tool_call],
                trace=trace,
            )

        if tool_call.name != "search_notes":
            trace.append(AgentTraceStep(step_type="answer", reason="模型选择了未知工具。"))
            return AgentAskResponse(
                question=request.question,
                answer=f"模型选择了未知工具：{tool_call.name}",
                used_retrieval=False,
                sources=[],
                tool_calls=[tool_call],
                trace=trace,
            )

        query = str(tool_call.arguments.get("query") or request.question)
        top_k = _tool_top_k(tool_call, default=request.top_k)
        raw_results = self.retrieval_service.search(query, top_k=top_k, mode=request.mode, filters=request.filters)
        results = [_as_search_result(result) for result in raw_results]
        trace.append(
            AgentTraceStep(
                step_type="tool_result",
                tool_name="search_notes",
                query=query,
                result_count=len(results),
                results=[to_search_hit(result) for result in results],
            )
        )

        if not results:
            trace.append(AgentTraceStep(step_type="answer", reason="工具没有返回足够证据。"))
            return AgentAskResponse(
                question=request.question,
                answer="本地知识库没有足够相关资料来回答这个问题。",
                used_retrieval=True,
                sources=[],
                tool_calls=[tool_call],
                trace=trace,
            )

        final_messages = [
            *messages,
            _assistant_tool_call_message(tool_response.content, tool_call),
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": _tool_result_content(results),
            },
        ]
        answer = chat_client.complete(final_messages).strip()
        if not answer:
            answer = _fallback_evidence_answer(results)
        trace.append(AgentTraceStep(step_type="answer", reason="模型读取 tool result 后生成最终答案。"))
        return AgentAskResponse(
            question=request.question,
            answer=answer,
            used_retrieval=True,
            sources=format_sources(results),
            tool_calls=[tool_call],
            trace=trace,
        )

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def _fallback_response(question: str, reason: str) -> AgentAskResponse:
    return AgentAskResponse(
        question=question,
        answer=reason,
        used_retrieval=False,
        sources=[],
        tool_calls=[],
        trace=[AgentTraceStep(step_type="answer", reason=reason)],
    )


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
    payload = []
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
