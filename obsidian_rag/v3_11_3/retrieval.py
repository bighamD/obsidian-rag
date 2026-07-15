from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from obsidian_rag.v1.schemas import SearchMode, to_search_hit
from obsidian_rag.v3_11_3.schemas import CollectionSearchHit


class MultiCollectionRetrievalService:
    """在有限 collection scope 内复用现有 RetrievalService，并执行第二层 RRF。"""

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    def search(
        self,
        query: str,
        collections: list[str],
        *,
        top_k: int,
        mode: SearchMode,
    ) -> tuple[list[CollectionSearchHit], dict[str, int], dict[str, str]]:
        recall_k = max(top_k * 3, top_k)
        results_by_collection: dict[str, list] = {}
        errors: dict[str, str] = {}

        if len(collections) == 1:
            collection = collections[0]
            try:
                results_by_collection[collection] = list(
                    self.retrieval_service.search(query, top_k=recall_k, mode=mode, collection=collection)
                )
            except Exception as exc:
                errors[collection] = _safe_error(exc)
        elif collections:
            with ThreadPoolExecutor(max_workers=len(collections)) as executor:
                futures = {
                    executor.submit(
                        self.retrieval_service.search,
                        query,
                        top_k=recall_k,
                        mode=mode,
                        collection=collection,
                    ): collection
                    for collection in collections
                }
                for future in as_completed(futures):
                    collection = futures[future]
                    try:
                        results_by_collection[collection] = list(future.result())
                    except Exception as exc:
                        errors[collection] = _safe_error(exc)

        hits = cross_collection_rrf(results_by_collection, top_k=top_k)
        counts = {collection: len(results_by_collection.get(collection, [])) for collection in collections if collection not in errors}
        return hits, counts, errors


def cross_collection_rrf(
    results_by_collection: dict[str, list],
    *,
    top_k: int,
    rank_constant: int = 60,
) -> list[CollectionSearchHit]:
    """按 collection 内排名融合；collection 是去重 key 的一部分。"""

    by_key: dict[str, CollectionSearchHit] = {}
    for collection, results in results_by_collection.items():
        for rank, result in enumerate(results, start=1):
            search_hit = to_search_hit(result)
            key = _result_key(collection, search_hit)
            score = 1 / (rank_constant + rank)
            existing = by_key.get(key)
            if existing is not None:
                by_key[key] = existing.model_copy(
                    update={"cross_collection_score": existing.cross_collection_score + score}
                )
                continue
            metadata = {**search_hit.metadata, "collection": collection}
            by_key[key] = CollectionSearchHit(
                **search_hit.model_dump(exclude={"metadata"}),
                metadata=metadata,
                collection=collection,
                collection_rank=rank,
                cross_collection_score=score,
            )
    fused = sorted(
        by_key.values(),
        key=lambda item: (-item.cross_collection_score, item.collection, item.collection_rank),
    )
    return fused[:top_k]


def _result_key(collection: str, hit) -> str:
    node_id = hit.metadata.get("node_id")
    if node_id:
        return f"{collection}:node_id:{node_id}"
    if hit.chunk_id:
        return f"{collection}:chunk_id:{hit.chunk_id}"
    chunk_index = hit.metadata.get("chunk_index", "")
    return f"{collection}:{hit.source}:{chunk_index}:{hit.text_preview[:80]}"


def _safe_error(exc: Exception) -> str:
    return (str(exc).strip() or type(exc).__name__)[:500]
