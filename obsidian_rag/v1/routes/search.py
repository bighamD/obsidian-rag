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
    search_kwargs = {
        "top_k": request.top_k,
        "mode": request.mode,
        "filters": request.filters,
    }
    if request.collection is not None:
        search_kwargs["collection"] = request.collection
    results = retrieval_service.search(
        request.query,
        **search_kwargs,
    )
    return SearchResponse(
        query=request.query,
        mode=request.mode,
        collection=_effective_collection_name(retrieval_service, request.collection),
        results=[to_search_hit(result) for result in results],
    )


@router.post("/compare-search", response_model=CompareSearchResponse)
def compare_search(
    request: SearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> CompareSearchResponse:
    compare_kwargs = {"top_k": request.top_k, "filters": request.filters}
    if request.collection is not None:
        compare_kwargs["collection"] = request.collection
    results = retrieval_service.compare_search(
        request.query,
        **compare_kwargs,
    )
    return CompareSearchResponse(
        query=request.query,
        collection=_effective_collection_name(retrieval_service, request.collection),
        results={
            mode: [to_search_hit(result) for result in mode_results]
            for mode, mode_results in results.items()
        },
    )


def _effective_collection_name(retrieval_service, collection: str | None) -> str:
    resolver = getattr(retrieval_service, "collection_name", None)
    if callable(resolver):
        return str(resolver(collection))
    config = getattr(retrieval_service, "config", None)
    return collection or str(getattr(config, "collection_name", "obsidian_notes"))
