## ADDED Requirements

### Requirement: 可配置 reasoning stream
系统 SHALL 通过环境变量控制是否向 OpenAI-compatible provider 请求 reasoning，并 MUST 在关闭时保持现有 answer-only 行为。

#### Scenario: 开关关闭
- **WHEN** `RAG_REASONING_STREAM_ENABLED=false`
- **THEN** Chat Client 不传 reasoning effort，系统不发布 reasoning_delta

#### Scenario: 开关开启且 provider 支持
- **WHEN** `RAG_REASONING_STREAM_ENABLED=true` 且流中包含 reasoning_content
- **THEN** 系统发布独立 reasoning_delta，并继续发布最终 answer_delta

#### Scenario: 开关开启但 provider 不支持
- **WHEN** provider 只返回 content
- **THEN** 系统正常完成 answer stream，不因缺少 reasoning_content 失败

### Requirement: Reasoning 与最终答案隔离
Core MUST NOT 将 reasoning_delta 内容拼入最终 answer、Memory、sources 或最终可见字符数。

#### Scenario: Reasoning 和 answer 同时产生
- **WHEN** 同一次生成包含 reasoning_content 和 content
- **THEN** 完整响应 answer 只等于 content chunks 的拼接结果

### Requirement: Runtime 实时转发
V3.10.2 与 V3.11 Runtime SHALL 通过 SSE EventBus 实时转发 reasoning_delta，且 MUST NOT 为每个 reasoning chunk 扩大 RunRecord.events。

#### Scenario: Reasoning chunk 到达
- **WHEN** Core 发布 reasoning_delta
- **THEN** SSE 客户端收到同名事件并携带 message_id、sequence 和 delta

### Requirement: Agent Console 学习调试展示
Agent Console SHALL 在同一个 assistant 消息中独立展示 reasoningText，并 MUST 保持 answer delta 去重和终态对账语义不变。

#### Scenario: Reasoning 先于 answer 到达
- **WHEN** 前端先收到 reasoning_delta 后收到 answer_delta
- **THEN** 页面在“思考过程（学习调试）”区域增长 reasoning，同时在正文区域增长最终答案

#### Scenario: 旧后端无 reasoning
- **WHEN** SSE 只包含 progress 和 answer_delta
- **THEN** 页面不显示空的 reasoning 区域，答案流继续正常工作
