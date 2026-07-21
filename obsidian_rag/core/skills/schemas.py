from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SkillSelectionStatus = Literal[
    "selected",
    "forced",
    "no_skill",
    "disabled",
    "invalid_selection",
    "router_error",
]


class SkillManifest(BaseModel):
    """Skill 发现阶段使用的轻量元数据，不包含方法正文。"""

    name: str = Field(description="Skill 的稳定名称，也是 Router 返回的唯一标识。")
    description: str = Field(description="Skill 适用任务说明，会进入 Skill Router prompt。")
    triggers: list[str] = Field(default_factory=list, description="帮助 Router 判断适用场景的关键词。")
    version: str = Field(default="1.0", description="Skill 文档版本。")
    entry_file: str = Field(default="SKILL.md", description="Skill 方法正文入口文件名。")
    path: str = Field(description="Skill 文档相对 Skill Root 的路径。")


class SkillDocument(SkillManifest):
    """选中后按需加载的完整 Skill 方法文档，仅在 Agent 内部进入 Planner Context。"""

    content: str = Field(description="SKILL.md 方法正文；不会默认完整返回给 Console。")
    estimated_tokens: int = Field(ge=0, description="Skill 正文的启发式 token 估算。")


class SkillLoadedSummary(SkillManifest):
    """允许返回给 API 和 Console 的 Skill 加载摘要，不包含完整方法正文。"""

    estimated_tokens: int = Field(ge=0, description="已注入 Planner Context 的 Skill 正文估算 token。")

    @classmethod
    def from_document(cls, document: SkillDocument) -> "SkillLoadedSummary":
        payload = document.model_dump(exclude={"content"})
        return cls.model_validate(payload)


class SkillSelection(BaseModel):
    """Skill Router 的结构化决定，不包含模型隐藏推理。"""

    status: SkillSelectionStatus = Field(description="Skill 选择状态。")
    selected_skill: str | None = Field(default=None, description="最终选择的 Skill；未选中时为 null。")
    reason: str = Field(description="面向调试的可观察选择原因。")
    confidence: float | None = Field(default=None, ge=0, le=1, description="LLM Router 置信度。")
    candidate_names: list[str] = Field(default_factory=list, description="本轮 Router 实际看到的候选 Skill。")
