from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from obsidian_rag.core.skills.schemas import SkillManifest, SkillSelection


class SkillRouterDecision(BaseModel):
    """LLM Skill Router 必须返回的最小结构化决定。"""

    skill_name: str | None = Field(default=None)
    reason: str = Field(default="未提供选择原因")
    confidence: float | None = Field(default=None, ge=0, le=1)


class LlmSkillRouter:
    """使用 LLM 从候选 Skill manifests 中选择零个或一个。"""

    SYSTEM_PROMPT = """你是一个 Skill Router。Skill 是完成一类任务的方法说明，不是工具。
请根据用户问题和候选 Skill 的描述，选择最适合的一个 Skill；如果没有明显匹配，返回 null。
只返回 JSON，不要 Markdown，不要输出隐藏推理：
{"skill_name":"skill-name 或 null","reason":"简短可观察原因","confidence":0.0}"""

    def __init__(self, chat_client=None, chat_client_factory=None):
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def route(self, question: str, candidates: list[SkillManifest]) -> SkillSelection:
        names = [candidate.name for candidate in candidates]
        if not candidates:
            return SkillSelection(status="no_skill", reason="Skill Registry 没有发现候选 Skill。")
        try:
            raw = self._client().complete(self._messages(question, candidates))
            decision = SkillRouterDecision.model_validate(json.loads(_extract_json(raw)))
        except (RuntimeError, ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return SkillSelection(
                status="router_error",
                reason=f"Skill Router 未返回可解析 JSON，已跳过 Skill：{exc}",
                candidate_names=names,
            )
        if decision.skill_name is None:
            return SkillSelection(
                status="no_skill",
                reason=decision.reason,
                confidence=decision.confidence,
                candidate_names=names,
            )
        if decision.skill_name not in names:
            return SkillSelection(
                status="invalid_selection",
                reason=f"LLM 选择了未知 Skill {decision.skill_name}，已安全跳过。",
                confidence=decision.confidence,
                candidate_names=names,
            )
        return SkillSelection(
            status="selected",
            selected_skill=decision.skill_name,
            reason=decision.reason,
            confidence=decision.confidence,
            candidate_names=names,
        )

    def _client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        if self.chat_client is None:
            raise RuntimeError("Skill Router 需要 LLM client")
        return self.chat_client

    def _messages(self, question: str, candidates: list[SkillManifest]) -> list[dict[str, str]]:
        payload = {
            "question": question,
            "candidates": [
                {
                    "name": item.name,
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
