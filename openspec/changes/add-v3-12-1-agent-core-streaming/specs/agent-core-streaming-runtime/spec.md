## ADDED Requirements

### Requirement: 无版本号公共 Agent Core
系统 SHALL 提供不依赖任何 `obsidian_rag.v3_x` 学习目录的公共 Agent Core，承载稳定的 Agent request/response/state、Context、Memory、Evidence、Tool 和 Event contract。

#### Scenario: 公共 Core 依赖方向
- **WHEN** 检查 `obsidian_rag/core/` 的 import
- **THEN** 不得出现对 `obsidian_rag.v3_` 学习版本目录的依赖

#### Scenario: 当前主线迁移
- **WHEN** V3.10、V3.10.2 或 V3.11 构建 Agent
- **THEN** 当前主线 SHALL 通过公共 Core 或兼容 Adapter 执行，不再直接 import V3.8.1 AgentService

### Requirement: 行为兼容迁移
公共 Core SHALL 保持迁移前 Planner、Retrieval、Evidence、Context、Memory 和最终 Answer 的主要语义，现有 JSON response 和终态 SSE contract MUST 保持兼容。

#### Scenario: 同步 JSON 调用
- **WHEN** 调用迁移后的同步 Agent JSON 接口
- **THEN** 系统返回完整 answer、sources、plan、context、memory 和 trace，不要求客户端消费流式事件

#### Scenario: 现有评估用例
- **WHEN** 使用现有 V3.9 Agent Evaluation cases 对迁移前后行为进行回归
- **THEN** routing、plan、tool、retrieval、evidence 和 answer contract 不因目录迁移而改变

### Requirement: 可见答案增量流
公共 Answer 节点 SHALL 支持把模型最终可见 `content` 作为 `answer_delta` 事件发布，并 MUST 在同一次模型调用中聚合出最终完整答案。

#### Scenario: Provider 支持 streaming
- **WHEN** Answer Chat Client 返回多个可见文本 chunk
- **THEN** SSE 按顺序发布多个 `answer_delta`，且拼接结果等于终态 response 的 answer

#### Scenario: Provider 不支持 streaming
- **WHEN** Chat Client 没有 streaming 能力或 streaming 在首个 chunk 前不可用
- **THEN** 系统回退 `complete()` 并仍返回成功的最终 response

#### Scenario: 不暴露隐藏推理
- **WHEN** Provider 同时提供 `reasoning_content` 和最终 `content`
- **THEN** `answer_delta` 只包含最终可见 `content`，不得包含隐藏推理

### Requirement: 可重放的 answer_delta contract
每个 `answer_delta` MUST 包含稳定 `message_id`、单调递增 `sequence`、`delta` 和 `node_name`，终态 response SHALL 继续作为权威结果。

#### Scenario: 增量顺序
- **WHEN** 同一答案产生连续文本 chunk
- **THEN** sequence 从 1 单调递增，所有事件使用同一个 message_id

#### Scenario: SSE 结束
- **WHEN** Agent 完成 Memory write 和 Run 生命周期
- **THEN** 系统发布包含完整结构化 response 的 `run_succeeded`，EventBus 随后关闭该 Run 的流

### Requirement: Agent Console 增量渲染
Agent Console SHALL 在请求开始时创建单个临时 assistant 消息，按 `message_id + sequence` 去重追加 `answer_delta`，并在终态响应到达后补齐来源、Run 和 Memory。

#### Scenario: 正常流式回答
- **WHEN** 前端依次收到多个 `answer_delta`
- **THEN** 同一个 assistant 气泡持续增长，不等待最终 response 才首次显示正文

#### Scenario: 最终响应对账
- **WHEN** 前端收到 `run_succeeded` 完整 response
- **THEN** 临时消息被最终 answer 和 sources 更新，不得再插入重复 assistant 消息

#### Scenario: 流中断
- **WHEN** SSE 在最终响应前失败
- **THEN** 前端保留已接收的可见答案并显示错误状态

### Requirement: 统一本地与 MCP Tool Registry
公共 Core SHALL 用统一 Tool Definition、arguments 和 ToolResult contract 注册本地 Tool 与 V3.12 MCP Tool Adapter，MCP Tool 名称 MUST 保留 `server::tool` 命名空间。

#### Scenario: 发现本地和 MCP Tool
- **WHEN** Registry 同时注册本地 search tool 和 MCP read-only tool
- **THEN** 调用方可通过统一 list contract 发现两类 Tool 及其参数 schema

#### Scenario: 显式执行 MCP Tool
- **WHEN** 调用方显式执行已注册的低风险 MCP Tool
- **THEN** Adapter 调用 V3.12 McpClientManager 并返回统一 ToolResult

#### Scenario: 未登记 Tool
- **WHEN** 调用方请求未知 Tool 名称
- **THEN** Registry 返回结构化失败结果，不执行任意外部调用

### Requirement: V3.12.1 学习闭环
V3.12.1 SHALL 提供独立目录、FastAPI JSON/SSE、CLI、Pydantic 中文字段说明、service/API/CLI 测试、学习文档、SVG 和可执行断点配置。

#### Scenario: Swagger 调试
- **WHEN** 用户启动 V3.12.1 FastAPI app
- **THEN** Swagger 可直接测试同步 ask、SSE 配置和统一 Tool Registry JSON 接口

#### Scenario: CLI 流式调试
- **WHEN** 用户运行 V3.12.1 stream CLI
- **THEN** CLI 实时打印 `answer_delta` 并在结束时输出完整结构化响应

### Requirement: 流式性能观测
系统 SHALL 记录最终 Answer 的首个可见 token 延迟和生成阶段耗时，且这些指标不得包含 Prompt 或模型隐藏推理。

#### Scenario: 成功流式生成
- **WHEN** Answer streaming 正常完成
- **THEN** Run/trace 提供 `llm_ttft_ms`、`llm_generation_ms` 和可见字符数

#### Scenario: 非流式回退
- **WHEN** Answer 使用 `complete()` 回退
- **THEN** 指标明确标记非流式模式，`llm_ttft_ms` 可为空
