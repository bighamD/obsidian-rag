from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from obsidian_rag.schema import SearchResult, TextChunk


@dataclass(frozen=True)
class KeywordIndexItem:
    text: str
    metadata: dict[str, Any]


class KeywordIndex:
    def __init__(self, path: Path):
        self.path = path
        self._items: list[KeywordIndexItem] = []
        self._doc_tokens: list[list[str]] = []
        self._doc_freqs: dict[str, int] = {}
        self._avg_doc_len = 0.0

    def build(self, chunks: list[TextChunk]) -> None:
        self._items = [KeywordIndexItem(text=chunk.text, metadata=chunk.metadata) for chunk in chunks]
        self._rebuild_stats()

    def load(self) -> None:
        if not self.path.exists():
            self._items = []
            self._rebuild_stats()
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._items = [
            KeywordIndexItem(text=str(item["text"]), metadata=dict(item.get("metadata") or {}))
            for item in payload.get("items", [])
        ]
        self._rebuild_stats()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"items": [asdict(item) for item in self._items]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if not self._items and self.path.exists():
            self.load()
        if not self._items:
            return []

        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        scored: list[SearchResult] = []
        for item, doc_tokens in zip(self._items, self._doc_tokens, strict=True):
            score = self._bm25_score(query_tokens, doc_tokens)
            if score > 0:
                scored.append(SearchResult(chunk=TextChunk(text=item.text, metadata=item.metadata), score=score))

        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]

    def _rebuild_stats(self) -> None:
        self._doc_tokens = [_tokens(_searchable_text(item)) for item in self._items]
        self._doc_freqs = {}
        for doc_tokens in self._doc_tokens:
            for token in set(doc_tokens):
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1
        total_length = sum(len(tokens) for tokens in self._doc_tokens)
        self._avg_doc_len = total_length / len(self._doc_tokens) if self._doc_tokens else 0.0

    def _bm25_score(self, query_tokens: list[str], doc_tokens: list[str]) -> float:
        if not doc_tokens or self._avg_doc_len == 0:
            return 0.0

        token_counts: dict[str, int] = {}
        for token in doc_tokens:
            token_counts[token] = token_counts.get(token, 0) + 1

        doc_count = len(self._doc_tokens)
        k1 = 1.5
        b = 0.75
        score = 0.0
        for token in query_tokens:
            freq = token_counts.get(token, 0)
            if freq == 0:
                continue
            doc_freq = self._doc_freqs.get(token, 0)
            idf = math.log(1 + (doc_count - doc_freq + 0.5) / (doc_freq + 0.5))
            denominator = freq + k1 * (1 - b + b * len(doc_tokens) / self._avg_doc_len)
            score += idf * (freq * (k1 + 1)) / denominator
        return score


def keyword_index_path(db_path: Path) -> Path:
    return db_path.parent / "keyword_index.json"


def _searchable_text(item: KeywordIndexItem) -> str:
    hidden_keys = {"docling", "raw_chunk_text", "parent_text", "matched_child_text", "pages"}
    metadata_values = " ".join(
        str(value) for key, value in item.metadata.items() if key not in hidden_keys and value is not None
    )
    return f"{metadata_values}\n{item.text}"


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    words = re.findall(r"[a-z0-9_:-]+", normalized)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    return words + chinese_chars
