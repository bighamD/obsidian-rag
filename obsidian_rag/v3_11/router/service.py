from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from obsidian_rag.llm import OpenAIChatClient
from obsidian_rag.v3_11.schemas import SkillManifest, SkillSelection


class SkillRouterDecision(BaseModel):
    """LLM Router 要返回的最小结构化 JSON。"""

    skill_name: str | None = Field(default=None)
    reason: str = Field(default="未提供选择原因")
    confidence: float | None = Field(default=None, ge=0, le=1)


class SkillRouter:
    """使用 LLM 在候选 Skill 中选择零个或一个。"""

    SYSTEM_PROMPT = """你是一个 Skill Router。Skill 是完成一类任务的方法说明，不是工具。
请根据用户问题和候选 Skill 的描述，选择最适合的一个 Skill；如果没有明显匹配，返回 null。
只返回 JSON，不要 Markdown，不要输出隐藏推理。格式必须是：
{"skill_name": "skill-name 或 null", "reason": "简短可观察原因", "confidence": 0.0}
confidence 必须是 0 到 1 的数字。"""

    def __init__(self, chat_client_factory=None, chat_client=None):
        self.chat_client = chat_client
        self.chat_client_factory = chat_client_factory

    def route(self, question: str, candidates: list[SkillManifest]) -> SkillSelection:
        names = [candidate.name for candidate in candidates]
        if not candidates:
            return SkillSelection(
                status="no_skill",
                reason="Registry 没有发现可用 Skill。",
                candidate_names=[],
            )
        try:
            raw_output = self._client().complete(self._messages(question, candidates))
            decision = _parse_decision(raw_output)
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
                reason=f"LLM 选择了未知 Skill {decision.skill_name}，已安全降级为不加载。",
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

    def _client(self) -> OpenAIChatClient:
        if self.chat_client is not None:
            return self.chat_client
        if self.chat_client_factory is not None:
            return self.chat_client_factory()
        raise RuntimeError("SkillRouter 需要 chat_client 或 chat_client_factory")

    def _messages(self, question: str, candidates: list[SkillManifest]) -> list[dict[str, str]]:
        candidate_payload = [
            {
                "name": candidate.name,
                "description": candidate.description,
                "triggers": candidate.triggers,
            }
            for candidate in candidates
        ]
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"question": question, "candidates": candidate_payload},
                    ensure_ascii=False,
                ),
            },
        ]


def _parse_decision(raw_output: str) -> SkillRouterDecision:
    payload_text = _extract_json(raw_output)
    payload: dict[str, Any] = json.loads(payload_text)
    return SkillRouterDecision(**payload)


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
