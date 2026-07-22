from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from obsidian_rag.core.skills.schemas import SkillCandidate, SkillManifest, SkillSelection


class SkillRouterDecision(BaseModel):
    """LLM Skill Router 必须返回的最小结构化决定。"""

    skill_names: list[str] = Field(default_factory=list)
    skill_name: str | None = Field(default=None, description="兼容旧 Router 响应的单数 Skill。")
    reason: str = Field(default="未提供选择原因")
    confidence: float | None = Field(default=None, ge=0, le=1)


class LlmSkillRouter:
    """仅在候选存在歧义时使用 LLM 选择零个、一个或多个隐式 Skills。"""

    SYSTEM_PROMPT = """你是一个 Skill Router。Skill 是完成一类任务的方法说明，不是工具。
explicit_skills 已由用户明确指定，必须保留；请只从 candidates 中选择额外需要的零个、一个或多个 Skills。
不要重复返回 explicit_skills，不要选择与当前问题无关的 Skill。
只返回 JSON，不要 Markdown，不要输出隐藏推理：
{"skill_names":["skill-name"],"reason":"简短可观察原因","confidence":0.0}"""

    def __init__(self, chat_client=None, chat_client_factory=None):
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def route(
        self,
        question: str,
        candidates: list[SkillManifest],
        *,
        explicit_skill_names: list[str] | None = None,
        scored_candidates: list[SkillCandidate] | None = None,
        max_skills: int = 2,
    ) -> SkillSelection:
        names = [candidate.name for candidate in candidates]
        explicit = list(explicit_skill_names or [])
        if not candidates:
            return SkillSelection(
                status="forced" if explicit else "no_skill",
                selected_skill=explicit[0] if explicit else None,
                selected_skills=explicit,
                explicit_skills=explicit,
                reason="没有需要 LLM 判断的额外 Skill 候选。",
            )
        try:
            raw = self._client().complete(
                self._messages(question, candidates, explicit, scored_candidates or [])
            )
            decision = SkillRouterDecision.model_validate(json.loads(_extract_json(raw)))
        except (RuntimeError, ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return SkillSelection(
                status="router_error",
                reason=f"Skill Router 未返回可解析 JSON，已跳过 Skill：{exc}",
                selected_skill=explicit[0] if explicit else None,
                selected_skills=explicit,
                explicit_skills=explicit,
                candidate_names=names,
                candidates=scored_candidates or [],
                router_called=True,
            )
        selected_names = _stable_unique([*decision.skill_names, *([decision.skill_name] if decision.skill_name else [])])
        invalid_names = [name for name in selected_names if name not in names]
        if invalid_names:
            return SkillSelection(
                status="invalid_selection",
                selected_skill=explicit[0] if explicit else None,
                selected_skills=explicit,
                explicit_skills=explicit,
                reason=f"LLM 选择了未知 Skills：{', '.join(invalid_names)}，已忽略隐式结果。",
                confidence=decision.confidence,
                candidate_names=names,
                candidates=scored_candidates or [],
                router_called=True,
            )
        implicit = [name for name in selected_names if name not in explicit][:max_skills]
        combined = _stable_unique([*explicit, *implicit])
        if not combined:
            return SkillSelection(
                status="no_skill",
                reason=decision.reason,
                confidence=decision.confidence,
                candidate_names=names,
                candidates=scored_candidates or [],
                router_called=True,
            )
        return SkillSelection(
            status="selected",
            selected_skill=combined[0],
            selected_skills=combined,
            explicit_skills=explicit,
            implicit_skills=implicit,
            reason=decision.reason,
            confidence=decision.confidence,
            candidate_names=names,
            candidates=scored_candidates or [],
            router_called=True,
        )

    def _client(self):
        if self.chat_client is None and self.chat_client_factory is not None:
            self.chat_client = self.chat_client_factory()
        if self.chat_client is None:
            raise RuntimeError("Skill Router 需要 LLM client")
        return self.chat_client

    def _messages(
        self,
        question: str,
        candidates: list[SkillManifest],
        explicit_skill_names: list[str],
        scored_candidates: list[SkillCandidate],
    ) -> list[dict[str, str]]:
        scores = {item.name: item.score for item in scored_candidates}
        payload = {
            "question": question,
            "explicit_skills": explicit_skill_names,
            "candidates": [
                {
                    "name": item.name,
                    "description": item.description,
                    "triggers": item.triggers,
                    "match_score": scores.get(item.name),
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


def _stable_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
