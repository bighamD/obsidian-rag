from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from obsidian_rag.v3_10.schemas import ProductionAskRequest, ProductionAskResponse, RunStatus


class AgentStreamEvent(BaseModel):
    """一个通过 SSE 发送给前端的可观察事实事件。"""

    event_id: int = Field(description="当前 Run 内递增的事件编号。")
    run_id: str = Field(description="对应的 Production Run 标识。")
    name: str = Field(description="事件名称，例如 node_finished、trace_event 或 run_succeeded。")
    status: RunStatus = Field(description="事件发生时 Run 所处的生命周期状态。")
    occurred_at: str = Field(description="事件发生时间，UTC ISO 8601 格式。")
    detail: str = Field(description="面向用户和调试的简短事实说明。")
    data: dict[str, Any] = Field(default_factory=dict, description="事件结构化数据；不包含模型内部推理。")


class StreamConfigResponse(BaseModel):
    """V3.10.2 Console 使用的运行模式配置。"""

    api_mode: str = Field(description="当前 API 同时支持 json 和 sse。")
    streaming_available: bool = Field(description="当前 API 是否支持 SSE 实时事件。")
    stream_endpoint: str = Field(description="SSE POST 接口路径。")
    default_memory_window: int = Field(description="前端新会话默认携带的最近原始 Turn 数。")


__all__ = ["AgentStreamEvent", "ProductionAskRequest", "ProductionAskResponse", "StreamConfigResponse"]
