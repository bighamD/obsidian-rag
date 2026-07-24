## Why

V3.10、V3.10.2 和 V3.11 仍直接依赖 V3.8.1 学习目录，公共 Agent 能力缺少稳定依赖方向；同时 V3.10.3 已验证 `answer_delta`，但当前主线 SSE 和 Agent Console 仍要等待完整答案。V3.12.1 需要在进入 Permission Policy 前收敛公共 Core、Tool Adapter 和可见答案流，避免后续安全层继续建立在历史版本耦合之上。

## What Changes

- 新增无版本号 `obsidian_rag/core/`，承载稳定 Agent contract、LLM complete/stream adapter、Agent event 和统一 Tool Registry。
- 将 V3.8.1 Agent 内核通过公共 Core 暴露，并让 V3.10/V3.10.2/V3.11 当前主线不再直接 import `obsidian_rag.v3_8_1`；历史版本保留兼容入口。
- 将 V3.12 MCP Tool/Result 通过 Adapter 注册到公共 Tool Registry，保持显式、低风险调用边界，不增加 LLM 自动选高风险 Tool。
- 复用 V3.10.3 已验证的 OpenAI-compatible streaming，将最终可见答案发布为 `answer_delta`，并继续聚合完整答案用于 JSON、Memory 和 `run_succeeded`。
- Agent Console 在请求开始时创建临时 assistant 消息，按 `message_id + sequence` 增量追加文本，并用最终响应补齐来源、Run 和 Memory，避免重复消息。
- 新增独立 `obsidian_rag/v3_12_1/` FastAPI、CLI、Swagger、测试、调试配置、学习文档和 SVG；提供同步 JSON 与 SSE 对照入口。
- 增加 `llm_ttft_ms` 和 `llm_generation_ms` 等流式观测字段；不展示 `reasoning_content` 或隐藏推理。

## Capabilities

### New Capabilities

- `agent-core-streaming-runtime`: 公共 Agent Core、统一 Tool Adapter、向后兼容 JSON/SSE 契约和可见答案 `answer_delta` 流。

### Modified Capabilities

- 无；仓库尚未建立公共 Agent Core 的基线 OpenSpec capability。

## Impact

- 新增：`obsidian_rag/core/`、`obsidian_rag/v3_12_1/`、对应测试、文档和流程图。
- 调整：V3.10/V3.10.2/V3.11 的依赖组装、公共 LLM/Event/Tool 契约，以及 Agent Console SSE view model。
- 复用：V3.8.1 Agent 行为、V3.10.2 EventBus、V3.10.3 token streaming、V3.12 MCP Adapter。
- 对外兼容：现有 JSON response 和终态 SSE 保持可用；`answer_delta` 是新增的运行中事件。
- 非目标：不修改 Prompt、检索策略、Memory 语义，不实现 Permission、Sandbox、MCP Session Pool、fast path 或原始模型思维链展示。
