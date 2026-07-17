from __future__ import annotations

import math


def ranking_metrics(ids: list[str], relevant: set[str], top_k: int) -> dict[str, float]:
    ranked = ids[:top_k]
    hits = [1 if item in relevant else 0 for item in ranked]
    first = next((index for index, hit in enumerate(hits, start=1) if hit), None)
    dcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(hits, start=1))
    ideal_hits = [1] * min(len(relevant), top_k)
    idcg = sum(hit / math.log2(index + 1) for index, hit in enumerate(ideal_hits, start=1))
    return {
        "hit_at_k": 1.0 if any(hits) else 0.0,
        "recall_at_k": sum(hits) / len(relevant) if relevant else 0.0,
        "mrr": 1.0 / first if first else 0.0,
        "ndcg_at_k": dcg / idcg if idcg else 0.0,
    }


def mean_metrics(values: list[dict[str, float]]) -> dict[str, float]:
    if not values:
        return {"hit_at_k": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0}
    return {key: sum(value[key] for value in values) / len(values) for key in values[0]}
