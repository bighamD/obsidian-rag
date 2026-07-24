## Why

V3.12.1 已能通过 progress 和 answer_delta 提供真实运行反馈，但当前 OpenAI-compatible 客户端会丢弃 CPA 返回的 `reasoning_content`。学习阶段需要一条可开关、与最终答案严格隔离的 reasoning 流，用于理解 reasoning model 在首个 answer token 前后的输出行为。

## What Changes

- 增加 `.env` 开关和 reasoning effort 配置，关闭时保持当前请求与响应行为。
- OpenAI-compatible Chat Completions 流适配 `reasoning_content`，Core 发布独立 `reasoning_delta`。
- `reasoning_delta` 不拼入最终 answer，不写入 Memory、sources 或 Answer token 指标。
- V3.10.2/V3.11 Runtime 通过 SSE EventBus 转发 reasoning 事件。
- Agent Console 增加独立的“思考过程（学习调试）”实时区域，与最终答案分开显示。
- 增加后端、Runtime、前端 reducer 测试和 V3.12.1 学习文档说明。

## Capabilities

### New Capabilities

- `reasoning-delta-stream`: 可配置的 CPA reasoning_content 流适配、独立 SSE 契约和学习调试 UI。

### Modified Capabilities

- 无。

## Impact

- 配置：`.env`、`.env.example`、`obsidian_rag/config.py`。
- LLM/Core：`obsidian_rag/llm.py`、`obsidian_rag/core/llm.py`、`obsidian_rag/core/agent/service.py` 和 streaming metrics/schema。
- Runtime：V3.10.2 与 V3.11 SSE 转发白名单和 detail。
- 前端：Agent stream types、composable reducer、ChatTranscript 和样式。
- 兼容性：默认关闭 reasoning stream；不支持 `reasoning_content` 的模型继续只产生 answer_delta。
