from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from obsidian_rag.core.schemas import MemorySnapshot


class ConsoleFeatures(BaseModel):
    """当前 Console contract 支持的用户可见能力。"""

    model_config = ConfigDict(populate_by_name=True)

    json_api: bool = Field(alias="json", description="是否支持同步 JSON Agent 请求。")
    sse: bool = Field(description="是否支持 SSE Agent 请求。")
    answer_delta: bool = Field(description="是否支持最终答案文本增量事件。")
    reasoning_delta: bool = Field(description="当前是否启用学习调试 reasoning 增量事件。")
    conversation_memory: bool = Field(description="是否支持持久化会话 Memory 读取。")
    collections: bool = Field(description="Agent 请求是否支持指定知识库 collection。")


class ConsoleEndpoints(BaseModel):
    """Agent Console 在当前契约下使用的稳定 API 路径。"""

    ask: str = Field(description="同步 JSON Agent 请求路径。")
    stream: str = Field(description="SSE Agent 请求路径。")
    conversation: str = Field(description="按 conversation_id 读取会话快照的路径模板。")
    runs: str = Field(description="读取近期 Run 的路径。")


class ConsoleConfigResponse(BaseModel):
    """Agent Console 启动时执行能力协商的稳定响应。"""

    contract_version: Literal["console.v1"] = Field(description="前后端共享的 Console API 契约版本。")
    backend_version: str = Field(description="当前提供契约的学习版后端，仅用于展示和诊断。")
    features: ConsoleFeatures = Field(description="当前后端实际启用的 Console 能力。")
    endpoints: ConsoleEndpoints = Field(description="Console 使用的稳定 API 路径。")
    default_memory_window: int = Field(ge=0, le=20, description="新会话默认读取的最近原始 Turn 数。")


class ConsoleConversationResponse(BaseModel):
    """Agent Console 切换会话时读取的公共 Core Memory 快照。"""

    conversation_id: str = Field(description="浏览器当前选择的会话标识。")
    memory_snapshot: MemorySnapshot = Field(description="从 MySQL 读取的 Core 会话记忆快照。")
