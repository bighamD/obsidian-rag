from __future__ import annotations

import math
import re
from collections import Counter

from obsidian_rag.core.skills.schemas import SkillCandidate, SkillManifest


class SkillMatcher:
    """使用内存 BM25、词项覆盖率和 Trigger 为 Skill Manifest 排序。"""

    def match(self, question: str, manifests: list[SkillManifest]) -> list[SkillCandidate]:
        query_tokens = _tokens(question)
        if not query_tokens or not manifests:
            return []

        documents = [_tokens(_manifest_text(item)) for item in manifests]
        raw_bm25 = _bm25_scores(query_tokens, documents)
        max_bm25 = max(raw_bm25, default=0.0)
        query_token_set = set(query_tokens)
        candidates: list[SkillCandidate] = []

        for manifest, document_tokens, raw_score in zip(manifests, documents, raw_bm25, strict=True):
            normalized_bm25 = raw_score / max_bm25 if max_bm25 > 0 else 0.0
            document_token_set = set(document_tokens)
            overlap = len(query_token_set & document_token_set) / max(len(query_token_set), 1)
            matched_triggers = [trigger for trigger in manifest.triggers if trigger and trigger.lower() in question.lower()]
            trigger_score = min(1.0, len(matched_triggers) / max(min(len(manifest.triggers), 2), 1))
            score = 0.55 * normalized_bm25 + 0.25 * overlap + 0.20 * trigger_score
            if matched_triggers:
                score = max(score, 0.92)
            candidates.append(
                SkillCandidate(
                    name=manifest.name,
                    score=min(1.0, round(score, 6)),
                    bm25_score=round(normalized_bm25, 6),
                    overlap_score=round(overlap, 6),
                    trigger_score=round(trigger_score, 6),
                    matched_triggers=matched_triggers,
                )
            )

        return sorted(candidates, key=lambda item: (-item.score, item.name))


def _manifest_text(manifest: SkillManifest) -> str:
    return "\n".join([manifest.name.replace("-", " "), manifest.description, *manifest.triggers])


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    words = re.findall(r"[a-z0-9_:-]+", normalized)
    chinese_segments = re.findall(r"[\u4e00-\u9fff]+", normalized)
    chinese_tokens: list[str] = []
    for segment in chinese_segments:
        chinese_tokens.extend(segment)
        chinese_tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
    return words + chinese_tokens


def _bm25_scores(query_tokens: list[str], documents: list[list[str]]) -> list[float]:
    if not documents:
        return []
    document_count = len(documents)
    average_length = sum(len(document) for document in documents) / document_count or 1.0
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))

    scores: list[float] = []
    k1 = 1.5
    b = 0.75
    for document in documents:
        token_counts = Counter(document)
        score = 0.0
        for token in query_tokens:
            frequency = token_counts.get(token, 0)
            if frequency == 0:
                continue
            frequency_in_documents = document_frequency[token]
            inverse_document_frequency = math.log(
                1 + (document_count - frequency_in_documents + 0.5) / (frequency_in_documents + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * len(document) / average_length)
            score += inverse_document_frequency * (frequency * (k1 + 1)) / denominator
        scores.append(score)
    return scores
