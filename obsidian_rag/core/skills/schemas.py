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
SkillSelectionMode = Literal["augment", "exclusive"]
SkillRoutingPath = Literal["no_skill", "direct", "llm_router", "explicit_only", "disabled"]


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


class SkillCandidate(BaseModel):
    """Skill Manifest 轻量匹配产生的候选，不包含完整 SKILL.md。"""

    name: str = Field(description="候选 Skill 名称。")
    score: float = Field(ge=0, le=1, description="Trigger、BM25 和词项覆盖率融合后的候选分数。")
    bm25_score: float = Field(ge=0, le=1, description="本轮候选集合内归一化后的 BM25 分数。")
    overlap_score: float = Field(ge=0, le=1, description="用户问题词项被 Skill Manifest 覆盖的比例。")
    trigger_score: float = Field(ge=0, le=1, description="显式 Trigger 子串命中的归一化分数。")
    matched_triggers: list[str] = Field(default_factory=list, description="实际命中的 Trigger。")


class SkillRoutingDecision(BaseModel):
    """Matcher 后的确定性路由决定，用于判断是否需要 LLM Skill Router。"""

    path: SkillRoutingPath = Field(description="直接选择、不选、显式模式或升级 LLM Router。")
    selected_skill_names: list[str] = Field(default_factory=list, description="无需 LLM 时直接选中的隐式 Skills。")
    reason: str = Field(description="可观察的路由原因，不包含隐藏推理。")
    top_score: float | None = Field(default=None, ge=0, le=1, description="最高候选融合分数。")
    score_margin: float | None = Field(default=None, ge=0, le=1, description="第一名与第二名的分差。")


class SkillSelection(BaseModel):
    """Skill Router 的结构化决定，不包含模型隐藏推理。"""

    status: SkillSelectionStatus = Field(description="Skill 选择状态。")
    selected_skill: str | None = Field(default=None, description="最终选择的 Skill；未选中时为 null。")
    selected_skills: list[str] = Field(default_factory=list, description="最终按优先级排列并去重后的全部 Skills。")
    explicit_skills: list[str] = Field(default_factory=list, description="用户明确指定、必须保留的 Skills。")
    implicit_skills: list[str] = Field(default_factory=list, description="Matcher 或 LLM Router 补充的隐式 Skills。")
    reason: str = Field(description="面向调试的可观察选择原因。")
    confidence: float | None = Field(default=None, ge=0, le=1, description="LLM Router 置信度。")
    candidate_names: list[str] = Field(default_factory=list, description="Registry 发现或 LLM Router 实际接收的候选 Skill 名称。")
    candidates: list[SkillCandidate] = Field(default_factory=list, description="Matcher 产生的候选分数与命中依据。")
    routing_decision: SkillRoutingDecision | None = Field(default=None, description="是否升级到 LLM Router 的确定性决定。")
    router_called: bool = Field(default=False, description="本轮是否真正调用了 LLM Skill Router。")
