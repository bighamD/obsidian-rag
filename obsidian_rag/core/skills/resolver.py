from __future__ import annotations

from obsidian_rag.core.skills.registry import SkillRegistry
from obsidian_rag.core.skills.router import LlmSkillRouter
from obsidian_rag.core.skills.schemas import SkillDocument, SkillManifest, SkillSelection


class CoreSkillResolver:
    """组合 Skill Registry 与 LLM Router，向 Core Agent 提供稳定接口。"""

    def __init__(self, registry: SkillRegistry, router: LlmSkillRouter):
        self.registry = registry
        self.router = router

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
        router_enabled: bool,
    ) -> SkillSelection:
        names = [item.name for item in candidates]
        if skill_name:
            if skill_name not in names:
                return SkillSelection(
                    status="invalid_selection",
                    reason=f"请求指定了未知 Skill：{skill_name}。",
                    candidate_names=names,
                )
            return SkillSelection(
                status="forced",
                selected_skill=skill_name,
                reason="请求通过 skill_name 强制选择 Skill，跳过 LLM Router。",
                candidate_names=names,
            )
        if not router_enabled:
            return SkillSelection(
                status="disabled",
                reason="请求关闭了 Skill Router，本轮不加载 Skill。",
                candidate_names=names,
            )
        return self.router.route(question, candidates)

    def load(self, name: str) -> SkillDocument:
        return self.registry.load(name)
