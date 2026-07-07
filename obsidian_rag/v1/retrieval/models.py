from __future__ import annotations

from dataclasses import dataclass

from obsidian_rag.schema import TextChunk


@dataclass(frozen=True)
class RankedSearchResult:
    chunk: TextChunk
    score: float
    dense_rank: int | None = None
    keyword_rank: int | None = None
    dense_score: float | None = None
    keyword_score: float | None = None
    hybrid_score: float | None = None
