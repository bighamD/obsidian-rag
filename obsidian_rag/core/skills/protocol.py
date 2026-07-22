from __future__ import annotations

from typing import Protocol

from obsidian_rag.core.skills.schemas import SkillDocument, SkillManifest, SkillSelection, SkillSelectionMode


class SkillResolver(Protocol):
    """Core Agent 使用的 Skill 发现、选择和加载稳定接口。"""

    @property
    def root(self) -> str: ...

    @property
    def errors(self) -> list[str]: ...

    def list_manifests(self) -> list[SkillManifest]: ...

    def select(
        self,
        *,
        question: str,
        candidates: list[SkillManifest],
        skill_name: str | None,
        skill_names: list[str] | None = None,
        selection_mode: SkillSelectionMode = "augment",
        router_enabled: bool = True,
    ) -> SkillSelection: ...

    def load(self, name: str) -> SkillDocument: ...
