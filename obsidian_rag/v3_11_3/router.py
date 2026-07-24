from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_11_3.schemas import CollectionSelection, KnowledgeBaseManifest


class CollectionRouterDecision(BaseModel):
    """LLM Collection Router 必须返回的最小 JSON。"""

    knowledge_base_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="未提供选择原因")
    confidence: float | None = Field(default=None, ge=0, le=1)


class CollectionRouter:
    """让 LLM 从启用 Registry candidates 中选择有限知识库。"""

    SYSTEM_PROMPT = """你是 Collection Router，只决定本次问题应该检索哪些知识库。
只能从候选 knowledge_base id 中选择，最多选择请求指定的 max_collections 个；没有适用知识库时返回空列表。
只返回 JSON，不要 Markdown，不要输出隐藏推理。格式必须是：
{"knowledge_base_ids": ["id"], "reason": "简短可观察原因", "confidence": 0.0}
confidence 必须是 0 到 1 的数字。"""

    def __init__(self, chat_client_factory=None, chat_client=None):
        self.chat_client_factory = chat_client_factory
        self.chat_client = chat_client

    def route(
        self,
        question: str,
        candidates: list[KnowledgeBaseManifest],
        max_collections: int,
    ) -> CollectionSelection:
        candidate_ids = [candidate.id for candidate in candidates]
        if not candidates:
            return CollectionSelection(
                status="no_collection",
                reason="Registry 没有启用的知识库。",
                candidate_ids=[],
            )
        try:
            raw_output = self._client().complete(self._messages(question, candidates, max_collections))
            decision = _parse_decision(raw_output)
        except (RuntimeError, ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return CollectionSelection(
                status="router_error",
                reason=f"Collection Router 未返回可解析 JSON：{exc}",
                candidate_ids=candidate_ids,
            )

        selected_ids = decision.knowledge_base_ids
        if len(selected_ids) != len(set(selected_ids)):
            return CollectionSelection(
                status="invalid_selection",
                reason="Collection Router 返回了重复知识库 ID。",
                confidence=decision.confidence,
                candidate_ids=candidate_ids,
            )
        if len(selected_ids) > max_collections:
            return CollectionSelection(
                status="invalid_selection",
                reason=f"Collection Router 选择了 {len(selected_ids)} 个知识库，超过上限 {max_collections}。",
                confidence=decision.confidence,
                candidate_ids=candidate_ids,
            )
        by_id = {candidate.id: candidate for candidate in candidates}
        unknown_ids = [item for item in selected_ids if item not in by_id]
        if unknown_ids:
            return CollectionSelection(
                status="invalid_selection",
                reason=f"Collection Router 选择了未知知识库：{', '.join(unknown_ids)}。",
                confidence=decision.confidence,
                candidate_ids=candidate_ids,
            )
        if not selected_ids:
            return CollectionSelection(
                status="no_collection",
                reason=decision.reason,
                confidence=decision.confidence,
                candidate_ids=candidate_ids,
            )
        return CollectionSelection(
            status="selected" if len(selected_ids) == 1 else "multi_selected",
            selected_ids=selected_ids,
            selected_collections=[by_id[item].collection for item in selected_ids],
            reason=decision.reason,
            confidence=decision.confidence,
            candidate_ids=candidate_ids,
        )

    def _client(self) -> OpenAIChatClient:
        if self.chat_client is not None:
            return self.chat_client
        if self.chat_client_factory is not None:
            return self.chat_client_factory()
        raise RuntimeError("CollectionRouter 需要 chat_client 或 chat_client_factory")

    def _messages(
        self,
        question: str,
        candidates: list[KnowledgeBaseManifest],
        max_collections: int,
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "max_collections": max_collections,
                        "candidates": [
                            {
                                "id": candidate.id,
                                "collection": candidate.collection,
                                "description": candidate.description,
                                "triggers": candidate.triggers,
                            }
                            for candidate in candidates
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]


def _parse_decision(raw_output: str) -> CollectionRouterDecision:
    payload: dict[str, Any] = json.loads(_extract_json(raw_output))
    return CollectionRouterDecision.model_validate(payload)


def _extract_json(raw_output: str) -> str:
    text = raw_output.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("未找到 JSON 对象", text, 0)
    return text[start : end + 1]
