from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

from obsidian_rag.v1.schemas import SearchFilters, SearchHit, SearchMode
from obsidian_rag.v3_4.schemas import Plan


StepStatus = Literal["success", "skipped", "failed"]
AgentTraceStepType = Literal[
    "memory_read",
    "planner",
    "tool_result",
    "evidence_check",
    "retry",
    "context",
    "synthesize",
    "memory_write",
    "error",
]


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=120)
    memory_window: int = Field(default=3, ge=0, le=20)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: SearchMode = "hybrid"
    filters: SearchFilters | None = None
    max_steps: int = Field(default=4, ge=1, le=8)
    max_retries: int = Field(default=1, ge=0, le=3)
    context_max_chunks: int = Field(default=6, ge=1, le=20)
    context_token_budget: int = Field(default=4000, ge=500, le=20000)


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


class ContextChunk(BaseModel):
    step_id: str | None = None
    chunk_id: str | None = None
    source: str
    topic: str | None = None
    score: float
    text_preview: str
    reason: str | None = None


class ContextBundle(BaseModel):
    messages: list[dict[str, str]]
    included_chunks: list[ContextChunk] = Field(default_factory=list)
    excluded_chunks: list[ContextChunk] = Field(default_factory=list)
    token_budget: int
    context_summary: str


class MemoryTurn(BaseModel):
    turn_id: str
    conversation_id: str
    user_message: str
    assistant_message: str
    sources: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str

    @field_validator("created_at", mode="before")
    @classmethod
    def format_created_at_for_china(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%y-%m-%d %H:%M:%S")


class MemorySnapshot(BaseModel):
    conversation_id: str
    window: int
    recent_turns: list[MemoryTurn] = Field(default_factory=list)
    total_turn_count: int = 0
    loaded_turn_count: int = 0
    omitted_turn_count: int = 0


class MemoryWriteResult(BaseModel):
    conversation_id: str
    turn_id: str | None = None
    saved: bool
    reason: str | None = None


class AgentAskResponse(BaseModel):
    run_id: str
    conversation_id: str
    question: str
    answer: str
    used_retrieval: bool
    sources: list[str]
    plan: Plan
    step_results: list[StepResult]
    retry_step_results: list[StepResult]
    evidence_check: EvidenceCheckResult
    context_bundle: ContextBundle
    memory_snapshot: MemorySnapshot
    memory_write: MemoryWriteResult
    graph_path: list[str]
    trace: list[AgentTraceStep]
