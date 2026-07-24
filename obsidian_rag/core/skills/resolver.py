from __future__ import annotations

from obsidian_rag.core.skills.registry import SkillRegistry
from obsidian_rag.core.skills.matcher import SkillMatcher
from obsidian_rag.core.skills.policy import SkillRoutingPolicyConfig, need_llm_skill_router
from obsidian_rag.core.skills.router import LlmSkillRouter
from obsidian_rag.core.skills.schemas import SkillDocument, SkillManifest, SkillSelection, SkillSelectionMode


class CoreSkillResolver:
    """组合 Skill Registry 与 LLM Router，向 Core Agent 提供稳定接口。"""

    def __init__(
        self,
        registry: SkillRegistry,
        router: LlmSkillRouter,
        matcher: SkillMatcher | None = None,
        policy_config: SkillRoutingPolicyConfig | None = None,
    ):
        self.registry = registry
        self.router = router
        self.matcher = matcher or SkillMatcher()
        self.policy_config = policy_config or SkillRoutingPolicyConfig()

    @property
    def root(self) -> str:
        return str(self.registry.root)

    @property
    def errors(self) -> list[str]:
        return list(self.registry.errors)

    def list_manifests(self) -> list[SkillManifest]:
        return self.registry.list_manifests()

    def select(
        self,
        *,
        question: str,
        candidates: list[SkillManifest],
        skill_name: str | None,
        skill_names: list[str] | None = None,
        selection_mode: SkillSelectionMode = "augment",
        router_enabled: bool = True,
    ) -> SkillSelection:
        names = [item.name for item in candidates]
        explicit = _stable_unique([*(skill_names or []), *([skill_name] if skill_name else [])])
        unknown = [name for name in explicit if name not in names]
        if unknown:
            return SkillSelection(
                status="invalid_selection",
                reason=f"请求指定了未知 Skills：{', '.join(unknown)}。",
                explicit_skills=explicit,
                candidate_names=names,
            )
        if selection_mode == "exclusive":
            if not explicit:
                return SkillSelection(
                    status="no_skill",
                    reason="请求使用 exclusive 模式但未指定显式 Skill，本轮不加载 Skill。",
                    candidate_names=names,
                    routing_decision={
                        "path": "explicit_only",
                        "selected_skill_names": [],
                        "reason": "显式独占模式未提供 Skill。",
                    },
                )
            return SkillSelection(
                status="forced",
                selected_skill=explicit[0],
                selected_skills=explicit,
                explicit_skills=explicit,
                reason="请求使用 exclusive 模式，只加载显式 Skills，跳过隐式匹配和 LLM Router。",
                candidate_names=names,
                routing_decision={
                    "path": "explicit_only",
                    "selected_skill_names": [],
                    "reason": "显式独占模式。",
                },
            )
        if not router_enabled:
            if explicit:
                return SkillSelection(
                    status="forced",
                    selected_skill=explicit[0],
                    selected_skills=explicit,
                    explicit_skills=explicit,
                    reason="请求关闭了 Skill Router，仅加载显式 Skills。",
                    candidate_names=names,
                )
            return SkillSelection(
                status="disabled",
                reason="请求关闭了 Skill Router，本轮不加载 Skill。",
                candidate_names=names,
            )

        remaining = [item for item in candidates if item.name not in explicit]
        matched = self.matcher.match(question, remaining)
        routing_decision = need_llm_skill_router(matched, self.policy_config)
        if routing_decision.path == "no_skill":
            if explicit:
                return SkillSelection(
                    status="forced",
                    selected_skill=explicit[0],
                    selected_skills=explicit,
                    explicit_skills=explicit,
                    reason=f"保留显式 Skills；{routing_decision.reason}",
                    candidate_names=names,
                    candidates=matched,
                    routing_decision=routing_decision,
                )
            return SkillSelection(
                status="no_skill",
                reason=routing_decision.reason,
                candidate_names=names,
                candidates=matched,
                routing_decision=routing_decision,
            )
        if routing_decision.path == "direct":
            implicit = routing_decision.selected_skill_names[: self.policy_config.max_implicit_skills]
            selected = _stable_unique([*explicit, *implicit])
            return SkillSelection(
                status="selected" if implicit else "forced",
                selected_skill=selected[0] if selected else None,
                selected_skills=selected,
                explicit_skills=explicit,
                implicit_skills=implicit,
                reason=routing_decision.reason,
                confidence=routing_decision.top_score,
                candidate_names=names,
                candidates=matched,
                routing_decision=routing_decision,
            )

        matched_names = [item.name for item in matched[: self.policy_config.max_router_candidates]]
        manifests_by_name = {item.name: item for item in remaining}
        routed = self.router.route(
            question,
            [manifests_by_name[name] for name in matched_names if name in manifests_by_name],
            explicit_skill_names=explicit,
            scored_candidates=matched[: self.policy_config.max_router_candidates],
            max_skills=self.policy_config.max_implicit_skills,
        )
        return routed.model_copy(update={"routing_decision": routing_decision})

    def load(self, name: str) -> SkillDocument:
        return self.registry.load(name)


def _stable_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
