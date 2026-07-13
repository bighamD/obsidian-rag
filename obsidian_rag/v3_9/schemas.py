from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from obsidian_rag.v3_8_1.schemas import AgentAskRequest, AgentAskResponse


class AgentEvalExpectation(BaseModel):
    """一个 Agent Eval case 的可选断言集合。

    字段为 `None` 时跳过对应维度；空列表表示该维度应当没有任何结果，
    例如 `expected_tools=[]` 断言本次不应调用工具。
    """

    should_retrieve: bool | None = Field(default=None, description="是否预期 Agent 至少获得一条检索结果。")
    required_step_kinds: list[str] | None = Field(
        default=None,
        description="Plan 中必须包含的 step.kind，例如 search、synthesize 或 no_search。",
    )
    expected_tools: list[str] | None = Field(default=None, description="实际执行结果中应出现的工具名；空列表断言不调用工具。")
    expected_chunk_ids: list[str] | None = Field(default=None, description="search 结果中应命中的知识库 chunk_id。")
    expected_source_files: list[str] | None = Field(default=None, description="search 结果中应出现的知识库来源文件。")
    evidence_sufficient: bool | None = Field(default=None, description="Evidence Checker 的 is_sufficient 预期值。")
    expected_answer_points: list[str] | None = Field(default=None, description="最终答案必须包含的关键文本点。")


class AgentEvalCase(BaseModel):
    """一次可重复运行的集成 Agent 评测案例。"""

    id: str = Field(min_length=1, description="案例唯一标识，用于报告和回归定位。")
    request: AgentAskRequest = Field(description="传给 V3.8.1 AgentService 的实际请求。")
    expect: AgentEvalExpectation = Field(description="本案例需要验证的 Agent 行为与结果。")


class AgentEvalCheck(BaseModel):
    """一个可解释的评分维度结果，而非模型内部推理。"""

    name: str = Field(description="评分维度，例如 routing、tools 或 answer。")
    passed: bool = Field(description="该维度是否满足预期。")
    expected: Any = Field(description="来自 AgentEvalExpectation 的预期值。")
    actual: Any = Field(description="从 AgentAskResponse 提取到的实际值。")
    detail: str = Field(description="本次通过或失败的简要说明。")


class AgentEvalReport(BaseModel):
    """单 case 的 Agent 行为评分报告。"""

    case_id: str = Field(description="被评测案例的 id。")
    passed: bool = Field(description="所有启用的评分维度是否都通过。")
    score: float = Field(ge=0, le=1, description="通过维度数除以启用维度数的平均分。")
    checks: list[AgentEvalCheck] = Field(description="各可解释评分维度的结果。")
    agent_response: AgentAskResponse = Field(description="本次真实 Agent 运行的完整响应，便于定位失败节点。")


class AgentEvalDataset(BaseModel):
    """YAML 中的一组可批量回归的 Agent Eval cases。"""

    cases: list[AgentEvalCase] = Field(min_length=1, description="需要逐个运行并评测的 Agent cases。")


class AgentEvalSummary(BaseModel):
    """批量评测的聚合指标。"""

    case_count: int = Field(description="批量运行的案例总数。")
    passed_count: int = Field(description="全部启用断言均通过的案例数。")
    pass_rate: float = Field(ge=0, le=1, description="passed_count 除以 case_count。")
    mean_score: float = Field(ge=0, le=1, description="所有单 case score 的平均值。")


class AgentEvalDatasetReport(BaseModel):
    """批量运行后的汇总报告，可选地保存为 JSON 回归记录。"""

    summary: AgentEvalSummary = Field(description="批量评测的聚合结果。")
    cases: list[AgentEvalReport] = Field(description="每个 case 的完整评分报告。")
    output_path: str | None = Field(default=None, description="保存 JSON 报告的位置；未保存时为 null。")


class AgentEvalDatasetRequest(BaseModel):
    """Swagger 中运行本地 YAML Agent Eval 数据集的请求。"""

    dataset_path: str = Field(description="本地 Agent Eval YAML 数据集路径。")
    save: bool = Field(default=True, description="是否将批量报告保存为 JSON 文件。")
    output_path: str | None = Field(default=None, description="自定义 JSON 报告路径；为空时生成默认路径。")
