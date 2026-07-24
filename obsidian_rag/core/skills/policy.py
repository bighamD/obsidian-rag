from __future__ import annotations

from dataclasses import dataclass

from obsidian_rag.core.skills.schemas import SkillCandidate, SkillRoutingDecision


@dataclass(frozen=True)
class SkillRoutingPolicyConfig:
    min_score: float = 0.35
    high_confidence_score: float = 0.82
    min_margin: float = 0.15
    max_router_candidates: int = 5
    max_implicit_skills: int = 2


def need_llm_skill_router(
    candidates: list[SkillCandidate],
    config: SkillRoutingPolicyConfig | None = None,
) -> SkillRoutingDecision:
    """根据候选绝对分、分差和竞争数量决定是否升级到 LLM Router。"""

    policy = config or SkillRoutingPolicyConfig()
    relevant = [item for item in candidates if item.score >= policy.min_score]
    if not relevant:
        return SkillRoutingDecision(
            path="no_skill",
            reason=f"没有候选达到最低分 {policy.min_score:.2f}，不调用 LLM Router。",
            top_score=candidates[0].score if candidates else None,
        )

    top = relevant[0]
    runner_up = relevant[1] if len(relevant) > 1 else None
    margin = round(top.score - runner_up.score, 6) if runner_up else None
    if runner_up is None and (top.score >= policy.high_confidence_score or top.matched_triggers):
        return SkillRoutingDecision(
            path="direct",
            selected_skill_names=[top.name],
            reason="唯一候选达到高置信度或命中显式 Trigger，直接选择。",
            top_score=top.score,
        )
    if (
        runner_up is not None
        and top.score >= policy.high_confidence_score
        and margin is not None
        and margin >= policy.min_margin
    ):
        return SkillRoutingDecision(
            path="direct",
            selected_skill_names=[top.name],
            reason="第一名高置信度且明显领先第二名，直接选择。",
            top_score=top.score,
            score_margin=margin,
        )
    return SkillRoutingDecision(
        path="llm_router",
        reason="候选处于灰区、前两名接近或存在多个竞争候选，需要 LLM 判断是否单选或组合。",
        top_score=top.score,
        score_margin=margin,
    )
