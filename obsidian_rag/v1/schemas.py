from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.schema import SearchResult
from obsidian_rag.v1.retrieval.models import RankedSearchResult


SearchMode = Literal["dense", "keyword", "hybrid"]


class SearchFilters(BaseModel):
    path: str | None = None
    tag: str | None = None
    file_type: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    mode: SearchMode = "hybrid"
    filters: SearchFilters | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    mode: SearchMode = "hybrid"
    filters: SearchFilters | None = None


class IngestRequest(BaseModel):
    path: str | None = None
    recreate: bool = False


class SearchHit(BaseModel):
    chunk_id: str | None = None
    source: str
    topic: str | None = None
    score: float
    dense_rank: int | None = None
    keyword_rank: int | None = None
    dense_score: float | None = None
    keyword_score: float | None = None
    hybrid_score: float | None = None
    text_preview: str
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    results: list[SearchHit]


class CompareSearchResponse(BaseModel):
    query: str
    results: dict[str, list[SearchHit]]


class AskResponse(BaseModel):
    question: str
    answer: str
    results: list[SearchHit]
    sources: list[str]


class IngestResponse(BaseModel):
    document_count: int
    chunk_count: int


def to_search_hit(result: SearchResult | RankedSearchResult) -> SearchHit:
    metadata = result.chunk.metadata
    return SearchHit(
        chunk_id=_optional_str(metadata.get("chunk_id")),
        source=str(metadata.get("source", "unknown")),
        topic=_optional_str(metadata.get("topic") or metadata.get("title")),
        score=float(result.score),
        dense_rank=getattr(result, "dense_rank", None),
        keyword_rank=getattr(result, "keyword_rank", None),
        dense_score=getattr(result, "dense_score", None),
        keyword_score=getattr(result, "keyword_score", None),
        hybrid_score=getattr(result, "hybrid_score", None),
        text_preview=_preview(result.chunk.text),
        metadata=metadata,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _preview(text: str, max_length: int = 500) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[:max_length]}..."
