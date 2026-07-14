from __future__ import annotations

from pydantic import BaseModel, Field

from obsidian_rag.v3_8_1.schemas import MemorySnapshot


class ConsoleConversationResponse(BaseModel):
    """Agent Console 读取一个会话时使用的 JSON 响应。

    `memory_snapshot` 是 MySQL 中的已持久化对话记忆，不是浏览器临时消息列表；
    当前问题和本轮回答仍需通过 `/agent/ask` 的 `agent_response.memory_write` 判断是否落盘。
    """

    conversation_id: str = Field(description="浏览器正在查看的会话标识。")
    memory_snapshot: MemorySnapshot = Field(description="从 V3.10 MySQL Memory 数据库读取到的会话快照。")


class ConsoleConfigResponse(BaseModel):
    """提供给 Vite Agent Console 的非敏感默认展示配置。"""

    api_mode: str = Field(description="当前界面的请求模式；V3.10.1 固定为一次性 JSON。")
    streaming_available: bool = Field(description="当前 API 是否支持实时 SSE；本版固定为 false。")
    default_memory_window: int = Field(description="前端新会话默认携带的最近原始 Turn 数。")
