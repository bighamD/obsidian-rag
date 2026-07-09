from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.v1.schemas import SearchFilters, SearchHit, SearchMode
from obsidian_rag.v3_4.schemas import Plan


StepStatus = Literal["success", "skipped", "failed"]
AgentTraceStepType = Literal["planner", "tool_result", "evidence_check", "retry", "synthesize", "error"]


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: SearchMode = "hybrid"
    filters: SearchFilters | None = None
    max_steps: int = Field(default=4, ge=1, le=8)
    max_retries: int = Field(default=1, ge=0, le=3)


class StepResult(BaseModel):
    step_id: str
    kind: str
    tool_name: str | None = None
    query: str | None = None
    instruction: str | None = None
    status: StepStatus
    result_count: int = 0
    results: list[SearchHit] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    error: str | None = None
    reason: str | None = None


class AgentTraceStep(BaseModel):
    node_name: str
    step_type: AgentTraceStepType
    step_id: str | None = None
    tool_name: str | None = None
    query: str | None = None
    result_count: int | None = None
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceCheckResult(BaseModel):
    is_sufficient: bool
    missing_points: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    checked_step_ids: list[str] = Field(default_factory=list)
    missing_step_ids: list[str] = Field(default_factory=list)
    retry_count: int = 0
    reason: str


class AgentAskResponse(BaseModel):
    run_id: str
    question: str
    answer: str
    used_retrieval: bool
    sources: list[str]
    plan: Plan
    step_results: list[StepResult]
    retry_step_results: list[StepResult]
    evidence_check: EvidenceCheckResult
    graph_path: list[str]
    trace: list[AgentTraceStep]
