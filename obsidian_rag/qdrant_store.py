from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from obsidian_rag.debugging import debug_breakpoint
from obsidian_rag.schema import SearchResult, TextChunk


class QdrantVectorStore:
    def __init__(
        self,
        collection_name: str,
        embedding_dimensions: int,
        path: Path | None = None,
        url: str | None = None,
    ):
        if url is None and path is None:
            raise ValueError("Either url or path is required")
        if url is not None and path is not None:
            raise ValueError("Use either url or path, not both")

        self.path = path
        self.url = url
        if url is not None:
            self.client = QdrantClient(url=url)
        else:
            assert path is not None
            path.parent.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(path))
        self.collection_name = collection_name
        self.embedding_dimensions = embedding_dimensions

    def ensure_collection(self, recreate: bool = False) -> None:
        if recreate or not self._collection_exists():
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.embedding_dimensions,
                    distance=models.Distance.COSINE,
                ),
            )

    def upsert(self, chunks: list[TextChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        debug_breakpoint(
            "qdrant.before_upsert",
            collection=self.collection_name,
            chunk_count=len(chunks),
            vector_dimensions=len(vectors[0]) if vectors else 0,
            first_chunk=chunks[0] if chunks else None,
        )
        points = [
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, _stable_point_key(chunk))),
                vector=vector,
                payload={"text": chunk.text, "metadata": chunk.metadata},
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        debug_breakpoint("qdrant.after_upsert", collection=self.collection_name, point_count=len(points))

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
        results: list[SearchResult] = []
        for point in response.points:
            payload: dict[str, Any] = point.payload or {}
            metadata = payload.get("metadata") or {}
            text = str(payload.get("text") or "")
            results.append(SearchResult(chunk=TextChunk(text=text, metadata=metadata), score=float(point.score)))
        debug_breakpoint("qdrant.after_search", collection=self.collection_name, top_k=top_k, result_count=len(results))
        return results

    def close(self) -> None:
        """释放 embedded Qdrant 的文件锁。"""

        self.client.close()

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.collection_name)
            return True
        except Exception:
            return False


def _stable_point_key(chunk: TextChunk) -> str:
    node_id = chunk.metadata.get("node_id")
    if node_id:
        return str(node_id)
    source = chunk.metadata.get("source", "")
    chunk_index = chunk.metadata.get("chunk_index", "")
    return f"{source}:{chunk_index}:{chunk.text[:80]}"
