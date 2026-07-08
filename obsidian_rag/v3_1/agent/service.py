from __future__ import annotations

from obsidian_rag.prompting import build_rag_messages, format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import to_search_hit
from obsidian_rag.v3_1.schemas import AgentAskRequest, AgentAskResponse, AgentTraceStep


class AgentService:
    def __init__(self, router_service, retrieval_service, chat_client=None, chat_client_factory=None):
        self.router_service = router_service
        self.retrieval_service = retrieval_service
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def ask(self, request: AgentAskRequest) -> AgentAskResponse:
        router = self.router_service.route(request.question)
        trace = [
            AgentTraceStep(
                step_type="router",
                decision=router.action,
                reason=router.reason,
                query=router.search_query,
                metadata={"intent": router.intent},
            )
        ]

        if router.action == "no_search" or request.max_steps == 0:
            trace.append(AgentTraceStep(step_type="answer", reason="按 router 决策直接回答。"))
            return AgentAskResponse(
                question=request.question,
                answer=router.direct_answer or "这个问题不适合查询本地知识库。",
                used_retrieval=False,
                sources=[],
                router=router,
                trace=trace,
            )

        if router.action == "clarify":
            trace.append(AgentTraceStep(step_type="answer", reason="按 router 决策向用户追问。"))
            return AgentAskResponse(
                question=request.question,
                answer=router.clarifying_question or "可以补充一下你想查询的范围吗？",
                used_retrieval=False,
                sources=[],
                router=router,
                trace=trace,
            )

        query = router.search_query or request.question
        raw_results = self.retrieval_service.search(
            query,
            top_k=request.top_k,
            mode=request.mode,
            filters=request.filters,
        )
        results = [_as_search_result(result) for result in raw_results]
        trace.append(
            AgentTraceStep(
                step_type="search",
                tool_name="search_notes",
                query=query,
                result_count=len(results),
                results=[to_search_hit(result) for result in results],
            )
        )

        evidence_reason = "找到可用于回答的本地资料。" if results else "没有找到足够相关的本地资料。"
        trace.append(AgentTraceStep(step_type="evidence", reason=evidence_reason, result_count=len(results)))

        if not results:
            trace.append(AgentTraceStep(step_type="answer", reason="证据不足，拒绝硬答。"))
            return AgentAskResponse(
                question=request.question,
                answer="本地知识库没有足够相关资料来回答这个问题。",
                used_retrieval=True,
                sources=[],
                router=router,
                trace=trace,
            )

        chat_client = self._chat_client()
        if chat_client is None:
            answer = "已找到本地资料，但当前没有配置 LLM 客户端生成最终答案。"
        else:
            messages = build_rag_messages(request.question, results[: request.top_k])
            answer = chat_client.complete(messages)
        trace.append(AgentTraceStep(step_type="answer", reason="基于检索证据生成最终答案。"))

        return AgentAskResponse(
            question=request.question,
            answer=answer,
            used_retrieval=True,
            sources=format_sources(results),
            router=router,
            trace=trace,
        )

    def _chat_client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        return self.chat_client


def _as_search_result(result: SearchResult | RankedSearchResult) -> SearchResult:
    if isinstance(result, SearchResult):
        return result
    return SearchResult(chunk=result.chunk, score=result.score)

