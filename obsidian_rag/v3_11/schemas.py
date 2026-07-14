from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.v3_10.schemas import ProductionAskRequest, RunRecord
from obsidian_rag.v3_8_1.schemas import AgentAskResponse


SkillSelectionStatus = Literal[
    "selected",
    "forced",
    "no_skill",
    "disabled",
    "invalid_selection",
    "router_error",
]


class SkillAskRequest(ProductionAskRequest):
    """V3.11 Skill-aware Agent 的请求。

    除了新增的 Skill 路由参数，其余 RAG、Memory、Context 和 Runtime 参数
    继续复用 V3.10/3.8.1 的定义。
    """

    skill_router_enabled: bool = Field(
        default=True,
        description="是否在 Planner 前调用 LLM Skill Router；关闭后直接跳过技能选择。",
    )
    skill_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="仅用于调试的强制 Skill 名称；填写后跳过 LLM 路由并直接加载该 Skill。",
    )


class SkillManifest(BaseModel):
    """Skill 的轻量元数据；发现阶段只读取此信息，不读取完整正文。"""

    name: str = Field(description="Skill 的稳定名称，也是路由结果中的唯一标识。")
    description: str = Field(description="Skill 适用任务的简短描述，会提供给 LLM Router。")
    triggers: list[str] = Field(
        default_factory=list,
        description="帮助 Router 判断是否适用的关键词或任务提示。",
    )
    version: str = Field(default="1.0", description="Skill 文档版本。")
    entry_file: str = Field(default="SKILL.md", description="Skill 方法正文的入口文件名。")
    path: str = Field(description="Skill 文档在本地的相对路径，仅用于调试展示。")


class SkillDocument(SkillManifest):
    """被选中后才加载的 Skill 正文，以及注入 Planner 的上下文投影。"""

    content: str = Field(description="SKILL.md 的完整正文；用于 API 调试和学习观察。")
    estimated_tokens: int = Field(description="Skill 正文的启发式 token 估算，不是供应商 usage。")


class SkillSelection(BaseModel):
    """Skill Router 的结构化决策，不包含模型隐藏推理。"""

    status: SkillSelectionStatus = Field(description="技能选择状态，例如 selected、no_skill 或 router_error。")
    selected_skill: str | None = Field(default=None, description="最终选中的 Skill 名称；未选中时为 null。")
    reason: str = Field(description="面向调试的选择原因，不等同于 chain-of-thought。")
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Router 返回的置信度；解析失败或未选择时可能为 null。",
    )
    candidate_names: list[str] = Field(
        default_factory=list,
        description="本次 Router 实际看到的候选 Skill 名称。",
    )


class SkillTraceEvent(BaseModel):
    """Skill 层的可观察事件，用于 trace、Swagger 和 SSE。"""

    node_name: str = Field(description="Skill 层节点名称，例如 discover_skills 或 skill_router。")
    event_type: str = Field(description="事件类型，例如 candidates、selected、loaded 或 skipped。")
    selected_skill: str | None = Field(default=None, description="事件关联的 Skill 名称。")
    reason: str = Field(description="事件的可观察原因说明，不包含隐藏推理。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Skill 层调试元数据。")


class SkillAgentResponse(BaseModel):
    """V3.11 Skill 层和底层 V3.8.1 Agent 的组合响应。"""

    agent_response: AgentAskResponse = Field(
        description="复用的 V3.8.1 Agent 完整响应，包含 Plan、检索、Context、Memory 和答案。",
    )
    skill_selection: SkillSelection = Field(description="本次请求的 Skill Router 决策。")
    loaded_skill: SkillDocument | None = Field(
        default=None,
        description="按需加载的 Skill 正文；未命中 Skill 时为 null。",
    )
    graph_path: list[str] = Field(
        description="V3.11 外层 Skill 节点加上 V3.8.1 内层 Agent 节点的执行顺序。",
    )
    trace: list[SkillTraceEvent] = Field(
        default_factory=list,
        description="V3.11 Skill 层可观察轨迹；底层 Agent trace 位于 agent_response.trace。",
    )


class SkillProductionAskResponse(BaseModel):
    """V3.11 JSON/SSE 统一响应，复用 V3.10 Run 生命周期外壳。"""

    run: RunRecord = Field(description="V3.10 Production Run 的生命周期、耗时和错误摘要。")
    skill_result: SkillAgentResponse | None = Field(
        default=None,
        description="成功时的 Skill-aware Agent 结果；失败时为 null。",
    )


class SkillRuntimeConfigResponse(BaseModel):
    """可安全暴露给 Swagger 的 V3.11 运行配置。"""

    skill_root: str = Field(description="本次服务扫描 Skill 文档的根目录。")
    candidate_count: int = Field(description="当前 Registry 发现的有效 Skill 数量。")
    router_mode: str = Field(description="Skill Router 当前使用的模式，例如 LLM JSON + fallback。")
    run_store: str = Field(description="Run Store 实现类型；当前沿用进程内存存储。")


class SkillListResponse(BaseModel):
    """Skill 列表接口响应。"""

    skills: list[SkillManifest] = Field(description="当前 Registry 发现的 Skill 元数据列表。")
    errors: list[str] = Field(default_factory=list, description="发现阶段跳过的无效 Skill 文件及原因。")
