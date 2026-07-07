from __future__ import annotations

from fastapi import APIRouter, Depends

from obsidian_rag.v1.dependencies import get_retrieval_service
from obsidian_rag.v1.schemas import CompareSearchResponse, SearchRequest, SearchResponse, to_search_hit
from obsidian_rag.v1.services.retrieval_service import RetrievalService

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_notes(
    request: SearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    results = retrieval_service.search(
        request.query,
        top_k=request.top_k,
        mode=request.mode,
        filters=request.filters,
    )
    return SearchResponse(
        query=request.query,
        mode=request.mode,
        results=[to_search_hit(result) for result in results],
    )


@router.post("/compare-search", response_model=CompareSearchResponse)
def compare_search(
    request: SearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> CompareSearchResponse:
    results = retrieval_service.compare_search(
        request.query,
        top_k=request.top_k,
        filters=request.filters,
    )
    return CompareSearchResponse(
        query=request.query,
        results={
            mode: [to_search_hit(result) for result in mode_results]
            for mode, mode_results in results.items()
        },
    )
