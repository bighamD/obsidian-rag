from __future__ import annotations

from obsidian_rag.config import RagConfig
from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.prompting import build_rag_messages, format_sources
from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult
from obsidian_rag.v1.schemas import AskRequest
from obsidian_rag.v1.services.retrieval_service import RetrievalService


class AnswerService:
    def __init__(self, config: RagConfig, retrieval_service: RetrievalService):
        self.config = config
        self.retrieval_service = retrieval_service

    def answer(self, request: AskRequest) -> tuple[str, list[SearchResult]]:
        results = self.retrieval_service.search(
            request.question,
            top_k=request.top_k,
            mode=request.mode,
            filters=request.filters,
        )
        search_results = [_as_search_result(result) for result in results]
        if not search_results:
            return "本地知识库没有足够相关资料来回答这个问题。", []

        chat = OpenAIChatClient(api_key=self.config.api_key, base_url=self.config.base_url, model=self.config.chat_model)
        messages = build_rag_messages(request.question, search_results)
        return chat.complete(messages), search_results

    def sources(self, results: list[SearchResult]) -> list[str]:
        return format_sources(results)


def _as_search_result(result: SearchResult | RankedSearchResult) -> SearchResult:
    if isinstance(result, SearchResult):
        return result
    return SearchResult(chunk=result.chunk, score=result.score)
