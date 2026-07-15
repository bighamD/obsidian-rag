from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from obsidian_rag.core.tools import ToolDefinition
from obsidian_rag.v3_10.schemas import ProductionAskRequest, ProductionAskResponse


class CoreAskRequest(ProductionAskRequest):
    """V3.12.1 公共 Core Agent 输入，字段语义与 V3.10 保持兼容。"""


class CoreAskResponse(ProductionAskResponse):
    """V3.12.1 同步完整响应；Answer streaming 指标位于 agent_response.answer_stream。"""


class CoreStreamConfigResponse(BaseModel):
    """V3.12.1 JSON/SSE 与答案增量能力说明。"""

    json_endpoint: str = Field(description="返回完整结构化响应的同步 JSON 接口。")
    stream_endpoint: str = Field(description="推送节点事件、answer_delta 和终态响应的 SSE 接口。")
    answer_delta_enabled: bool = Field(description="是否启用最终可见答案增量。")
    hidden_reasoning_exposed: bool = Field(description="是否会向客户端暴露模型隐藏推理；本版固定为 false。")


class UnifiedToolDefinition(BaseModel):
    """公共 Tool Registry 中本地或 MCP Tool 的可发现描述。"""

    name: str = Field(description="Registry 中的唯一工具名；MCP 使用 server::tool。")
    description: str = Field(description="工具用途说明。")
    input_schema: dict[str, Any] = Field(description="工具参数 JSON Schema。")
    read_only: bool | None = Field(default=None, description="只读提示；不是 Permission Policy 结论。")
    source: str = Field(description="工具来源，例如 local 或 mcp。")

    @classmethod
    def from_core(cls, definition: ToolDefinition) -> "UnifiedToolDefinition":
        return cls(**definition.__dict__)


class UnifiedToolListResponse(BaseModel):
    """统一本地与 MCP Tool 的发现响应。"""

    tools: list[UnifiedToolDefinition] = Field(description="当前成功注册的 Tool 列表。")
    errors: dict[str, str] = Field(default_factory=dict, description="MCP Server 发现失败摘要。")


class UnifiedToolCallRequest(BaseModel):
    """显式执行公共 Registry 中一个 Tool。"""

    name: str = Field(min_length=1, description="Tool 唯一名称，例如 search_notes 或 demo::get_server_time。")
    arguments: dict[str, Any] = Field(default_factory=dict, description="满足 Tool input_schema 的调用参数。")


class UnifiedToolCallResponse(BaseModel):
    """本地与 MCP Tool 共享的稳定执行结果。"""

    name: str = Field(description="实际请求的 Tool 名称。")
    status: Literal["success", "failed"] = Field(description="统一调用状态。")
    data: Any = Field(default=None, description="本地检索结果或 MCP Tool 响应的 JSON 投影。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="来源、collection 或耗时等可观察元数据。")
    error: str | None = Field(default=None, description="失败摘要；成功时为 null。")


class CoreHealthResponse(BaseModel):
    """V3.12.1 FastAPI 健康响应。"""

    status: Literal["ok"] = Field(description="当前 API 进程健康状态。")
    version: Literal["v3.12.1"] = Field(description="当前学习版本。")
    core_package: str = Field(description="当前公共 Agent Core 包路径。")
