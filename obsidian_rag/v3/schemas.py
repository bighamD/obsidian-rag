from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.v1.schemas import SearchFilters, SearchHit, SearchMode


AgentDecision = Literal["no_search", "search"]
AgentStepType = Literal["decision", "search", "evidence", "answer"]


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: SearchMode = "hybrid"
    filters: SearchFilters | None = None
    max_steps: int = Field(default=2, ge=0, le=3)


class AgentTraceStep(BaseModel):
    step_type: AgentStepType
    decision: AgentDecision | None = None
    reason: str | None = None
    tool_name: str | None = None
    query: str | None = None
    result_count: int | None = None
    results: list[SearchHit] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentAskResponse(BaseModel):
    question: str
    answer: str
    used_retrieval: bool
    sources: list[str]
    trace: list[AgentTraceStep]
