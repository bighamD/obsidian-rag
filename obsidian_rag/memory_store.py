from __future__ import annotations

import math

from obsidian_rag.schema import SearchResult, TextChunk


class InMemoryVectorStore:
    def __init__(self, embedding_dimensions: int):
        self.embedding_dimensions = embedding_dimensions
        self._items: list[tuple[TextChunk, list[float]]] = []

    def upsert(self, chunks: list[TextChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        for vector in vectors:
            if len(vector) != self.embedding_dimensions:
                raise ValueError("vector dimension mismatch")
        self._items.extend(zip(chunks, vectors, strict=True))

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        scored = [
            SearchResult(chunk=chunk, score=_cosine_similarity(query_vector, vector))
            for chunk, vector in self._items
        ]
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
