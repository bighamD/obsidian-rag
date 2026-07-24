from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from obsidian_rag.core.collections.schemas import KnowledgeBaseManifest, RetrievalScope


class CollectionRouterDecision(BaseModel):
    """LLM Collection Router 必须返回的最小结构化决定。"""

    knowledge_base_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="未提供选择原因")
    confidence: float | None = Field(default=None, ge=0, le=1)


class LlmCollectionRouter:
    """让 LLM 从 Registry candidates 中选择有限知识库。"""

    SYSTEM_PROMPT = """你是 Collection Router，只决定当前问题应该检索哪些知识库。
只能从候选 knowledge_base id 中选择，最多选择 max_collections 个；没有适用知识库时返回空列表。
只返回 JSON，不要 Markdown，不要输出隐藏推理：
{"knowledge_base_ids":["id"],"reason":"简短可观察原因","confidence":0.0}"""

    def __init__(self, chat_client=None, chat_client_factory=None):
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def route(
        self,
        question: str,
        candidates: list[KnowledgeBaseManifest],
        max_collections: int,
        *,
        registry_path: str | None = None,
    ) -> RetrievalScope:
        candidate_ids = [item.id for item in candidates]
        if not candidates:
            return RetrievalScope(
                status="no_collection",
                reason="Registry 没有启用的知识库。",
                candidate_ids=[],
                registry_path=registry_path,
            )
        try:
            raw = self._client().complete(self._messages(question, candidates, max_collections))
            decision = CollectionRouterDecision.model_validate(json.loads(_extract_json(raw)))
        except (RuntimeError, ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return RetrievalScope(
                status="router_error",
                reason=f"Collection Router 未返回可解析 JSON：{exc}",
                candidate_ids=candidate_ids,
                registry_path=registry_path,
                errors={"router": str(exc)},
            )

        selected_ids = decision.knowledge_base_ids
        if len(selected_ids) != len(set(selected_ids)):
            return _invalid_scope("Collection Router 返回了重复知识库 ID。", candidate_ids, decision, registry_path)
        if len(selected_ids) > max_collections:
            return _invalid_scope(
                f"Collection Router 选择了 {len(selected_ids)} 个知识库，超过上限 {max_collections}。",
                candidate_ids,
                decision,
                registry_path,
            )
        by_id = {item.id: item for item in candidates}
        unknown = [item for item in selected_ids if item not in by_id]
        if unknown:
            return _invalid_scope(
                f"Collection Router 选择了未知知识库：{', '.join(unknown)}。",
                candidate_ids,
                decision,
                registry_path,
            )
        if not selected_ids:
            return RetrievalScope(
                status="no_collection",
                reason=decision.reason,
                confidence=decision.confidence,
                candidate_ids=candidate_ids,
                registry_path=registry_path,
            )
        return RetrievalScope(
            status="selected" if len(selected_ids) == 1 else "multi_selected",
            selected_ids=selected_ids,
            selected_collections=[by_id[item].collection for item in selected_ids],
            reason=decision.reason,
            confidence=decision.confidence,
            candidate_ids=candidate_ids,
            registry_path=registry_path,
        )

    def _client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        if self.chat_client is None:
            raise RuntimeError("Collection Router 需要 LLM client")
        return self.chat_client

    def _messages(self, question: str, candidates: list[KnowledgeBaseManifest], max_collections: int):
        payload = {
            "question": question,
            "max_collections": max_collections,
            "candidates": [
                {
                    "id": item.id,
                    "collection": item.collection,
                    "description": item.description,
                    "triggers": item.triggers,
                }
                for item in candidates
            ],
        }
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]


def _invalid_scope(reason, candidate_ids, decision, registry_path) -> RetrievalScope:
    return RetrievalScope(
        status="invalid_selection",
        reason=reason,
        confidence=decision.confidence,
        candidate_ids=candidate_ids,
        registry_path=registry_path,
    )


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
