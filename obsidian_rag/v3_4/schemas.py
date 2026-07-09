from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.v1.schemas import SearchFilters, SearchMode


PlanStepKind = Literal["search", "synthesize", "no_search", "clarify"]
PlannerTraceStepType = Literal["planner_prompt", "planner_output", "planner_error"]


class PlanRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: SearchMode = "hybrid"
    filters: SearchFilters | None = None
    max_steps: int = Field(default=4, ge=1, le=8)


class PlanStep(BaseModel):
    id: str = Field(min_length=1)
    kind: PlanStepKind
    query: str | None = None
    instruction: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    reason: str | None = None


class Plan(BaseModel):
    goal: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)


class PlannerTraceStep(BaseModel):
    node_name: str
    step_type: PlannerTraceStepType
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    question: str
    plan: Plan
    graph_path: list[str]
    trace: list[PlannerTraceStep]
