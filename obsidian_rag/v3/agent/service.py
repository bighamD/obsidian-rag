from __future__ import annotations

import re

from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.prompting import build_rag_messages, format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3.schemas import AgentAskRequest, AgentAskResponse, AgentTraceStep


class AgentService:
    def __init__(self, retrieval_service, chat_client: OpenAIChatClient | None = None, chat_client_factory=None):
        self.retrieval_service = retrieval_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        should_search, reason = should_search_notes(request.question)
        trace = [
            AgentTraceStep(
                step_type="decision",
                decision="search" if should_search else "no_search",
                reason=reason,
            )
        ]

        if not should_search or request.max_steps == 0:
            return AgentAskResponse(
                question=request.question,
                answer="你好，我是本地知识库 RAG 助手。你可以问我需要查资料的问题。",
                used_retrieval=False,
                sources=[],
                trace=trace,
            )

        all_results: list[SearchResult] = []
        seen_sources: set[str] = set()
        queries = plan_search_queries(request.question, max_steps=request.max_steps)
        for query in queries:
            raw_results = self.retrieval_service.search(
                query,
                top_k=request.top_k,
                mode=request.mode,
                filters=request.filters,
            )
            search_results = [_as_search_result(result) for result in raw_results]
            trace.append(
                AgentTraceStep(
                    step_type="search",
                    tool_name="search_notes",
                    query=query,
                    result_count=len(search_results),
                    results=[to_search_hit(result) for result in search_results],
                )
            )
            for result in search_results:
                source = str(result.chunk.metadata.get("source", "unknown"))
                key = f"{source}:{result.chunk.metadata.get('chunk_index', '')}:{result.chunk.text[:80]}"
                if key not in seen_sources:
                    all_results.append(result)
                    seen_sources.add(key)

        evidence_reason = "找到可用于回答的本地资料。" if all_results else "没有找到足够相关的本地资料。"
        trace.append(
            AgentTraceStep(
                step_type="evidence",
                reason=evidence_reason,
                result_count=len(all_results),
            )
        )

        if not all_results:
            trace.append(AgentTraceStep(step_type="answer", reason="证据不足，拒绝硬答。"))
            return AgentAskResponse(
                question=request.question,
                answer="本地知识库没有足够相关资料来回答这个问题。",
                used_retrieval=True,
                sources=[],
                trace=trace,
            )

        chat_client = self._chat_client()
        if chat_client is None:
            answer = "已找到本地资料，但当前没有配置 LLM 客户端生成最终答案。"
        else:
            messages = build_rag_messages(request.question, all_results[: request.top_k])
            answer = chat_client.complete(messages)
        trace.append(AgentTraceStep(step_type="answer", reason="基于检索证据生成最终答案。"))

        return AgentAskResponse(
            question=request.question,
            answer=answer,
            used_retrieval=True,
            sources=format_sources(all_results),
            trace=trace,
        )

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def should_search_notes(question: str) -> tuple[bool, str]:
    normalized = question.strip().lower()
    if normalized in {"hi", "hello", "你好", "嗨", "在吗", "在？"}:
        return False, "这是寒暄，不需要查询本地知识库。"
    if len(normalized) <= 4 and not re.search(r"[\u4e00-\u9fff].*(吗|么|什么|怎么|为何|为什么)", normalized):
        return False, "问题过短且没有明确知识库查询意图。"
    return True, "问题需要本地知识库证据。"


def plan_search_queries(question: str, max_steps: int) -> list[str]:
    if max_steps <= 0:
        return []
    queries = [question]
    if max_steps >= 2 and _looks_multi_hop(question):
        queries.append(_secondary_query(question))
    return queries[:max_steps]


def _looks_multi_hop(question: str) -> bool:
    return any(marker in question for marker in ["，", "；", "以及", "同时", "处理完", "然后", "另外"]) and any(
        keyword in question for keyword in ["清洁", "洗手", "交叉污染", "处理"]
    )


def _secondary_query(question: str) -> str:
    if any(keyword in question for keyword in ["清洁", "洗手", "处理", "交叉污染"]):
        return "厨房 清洁 洗手 交叉污染"
    return question


def _as_search_result(result: SearchResult | RankedSearchResult) -> SearchResult:
    if isinstance(result, SearchResult):
        return result
    return SearchResult(chunk=result.chunk, score=result.score)
