## Context

当前 `OpenAIChatClient.stream()` 只 yield `delta.content`，Core 将其转换为 `answer_delta`。实测 CPA 的 `gpt-5.4-mini` 在 Chat Completions 请求显式传入 `reasoning_effort=medium` 时，会在流中增加非标准 `delta.reasoning_content`；未传 reasoning effort 时只返回 content。官方 reasoning tokens 不可见，因此本能力明确定位为 CPA 学习调试扩展，而不是可移植的生产契约。

## Goals / Non-Goals

**Goals:**

- 用 `.env` 开关控制是否请求和展示 reasoning 流。
- 将 reasoning 与最终 answer、Memory、sources、token 指标严格隔离。
- 保持不支持 reasoning_content 的模型和关闭开关时完全兼容。
- 在同一个 assistant 消息中提供独立、可折叠的学习调试区域。

**Non-Goals:**

- 不把 reasoning 当作最终答案或事实依据。
- 不把 reasoning 写入 MySQL Conversation Memory。
- 不承诺兼容所有 OpenAI-compatible provider 的私有 thinking 字段。
- 不迁移到 Responses API 或实现 reasoning summary。

## Decisions

### 1. 配置显式开启，默认关闭

新增 `RAG_REASONING_STREAM_ENABLED=false` 和 `RAG_REASONING_EFFORT=medium`。只有开关开启时，OpenAIChatClient 才传 `reasoning_effort` 并解析 `reasoning_content`，避免无意改变旧版本延迟、费用和输出。

### 2. LLM stream 使用类型化 delta

公共 LLM contract 新增 `ChatStreamDelta(kind, text)`。OpenAIChatClient 将 CPA 的 `reasoning_content` 映射为 `kind=reasoning`，将 `content` 映射为 `kind=content`；Core 同时兼容旧测试和自定义客户端 yield 的纯字符串。

### 3. Core 发布独立 reasoning_delta

`_generate_answer()` 对 reasoning 使用独立 sequence，并发布 `reasoning_delta(message_id, sequence, delta)`；只把 content 累加到最终 answer。AnswerStreamMetrics 记录 reasoning 首包时间和字符数，但最终 visible_character_count 仍只计算 answer。

### 4. Runtime 不持久化每个 reasoning chunk

V3.10.2/V3.11 将 reasoning_delta 与 answer_delta 一样直接推送 EventBus，不追加到 RunRecord.events，避免长推理导致 Run 快照膨胀。

### 5. 前端独立展示和归并

ConsoleMessage 增加 reasoningText、reasoningSequence 和 reasoningMessageId。reducer 独立去重追加；ChatTranscript 使用 `<details>` 展示“思考过程（学习调试）”，不将其写入 message.text。最终响应只对账 answer/sources/summary，不覆盖 reasoningText。

## Risks / Trade-offs

- [CPA 字段不是官方稳定契约] → 适配集中在 OpenAIChatClient，缺少字段时静默退化为 answer-only。
- [泄露内部推理] → 默认关闭、UI 明确标注学习调试、后端 Memory 不保存。
- [reasoning 增加费用和延迟] → effort 可配置，用户可随时关闭开关恢复旧行为。
- [reasoning chunk 很多] → Runtime 不写 RunRecord；前端仅保留当前消息文本用于学习观察。
