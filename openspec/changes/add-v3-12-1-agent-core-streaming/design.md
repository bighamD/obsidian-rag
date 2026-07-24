## Context

V3.8.1 已形成当前最完整的 Agentic RAG 内核，但 V3.9、V3.10、V3.10.2 和 V3.11 仍直接 import 学习版本目录。V3.12 已验证 MCP Client/Server 与稳定 Tool/Result Adapter，尚未进入 Agent Tool Registry。V3.10.3 另外验证了 OpenAI-compatible `stream=True`、LangGraph `messages` stream 和 `answer_delta`，但该能力只存在于 Advanced Graph，V3.11 主线与 Agent Console 没有消费文本增量。

V3.12.1 位于 Permission Policy 之前。若不先稳定 Agent、Event 和 Tool 契约，V3.13 将不得不依赖多个历史学习目录，并重复实现本地 Tool、MCP Tool 和 SSE 的策略入口。

## Goals / Non-Goals

**Goals:**

- 建立不 import 任意 `obsidian_rag.v3_x` 的无版本号公共 Core。
- 保持 V3.8.1 的 Planner、Retrieval、Evidence、Context、Memory 和 Answer 行为。
- 让 V3.10/V3.10.2/V3.11 当前主线通过公共 Core 或兼容 Adapter 工作。
- 用统一 Tool Definition/Result/Registry 接纳本地 Tool 和 V3.12 MCP Tool Adapter。
- 将最终可见答案以 `answer_delta` 发布，同时聚合完整答案供 JSON、Memory 和终态事件使用。
- 让 Agent Console 安全地展示增量答案，并保持最终结构化响应为权威状态。

**Non-Goals:**

- 不改变 Prompt、Planner 决策、检索策略、Evidence 阈值或 Memory 语义。
- 不展示 `reasoning_content`、chain-of-thought 或模型隐藏推理。
- 不实现 Permission、Sandbox、MCP Session Pool、自动高风险 Tool 选择或 fast path。
- 不删除历史学习版本，也不要求一次迁移所有旧版本。

## Decisions

### 1. 公共 Core 拥有实现，历史版本只保留兼容入口

稳定的 schemas、Context、Memory、Compaction、Tool Registry 和 AgentService 迁入 `obsidian_rag/core/`。公共 Core 不允许 import `v3_x`；V3.8.1 保留教学代码和兼容契约，当前主线的 dependencies/schemas 改为依赖 Core。

选择实际提升实现而不是在 Core 中反向包装 V3.8.1，是为了建立单向依赖。迁移采用小步兼容方式，不同时删除历史文件。

### 2. Answer streaming 是 LLM Port 的可选能力

公共 Chat Client contract 保留 `complete(messages)`，并增加 `stream(messages)`。结构化 Router/Planner 继续使用 `complete()`；只有最终 Answer 节点消费 `stream()`。不支持 streaming 的 client 回退到 `complete()`，并保持最终响应可用。

复用 V3.10.3 对 OpenAI-compatible chunk 的处理，但不要求公共 Core 继承 LangChain `BaseChatModel`。Core 使用简单字符串 iterator，LangChain/LangGraph 适配留在 Adapter 层。

### 3. 同一 Answer 节点同时生成增量和完整答案

SSE 路径中，Answer 节点逐 chunk：

1. 记录首个可见 token 的 TTFT。
2. 发布 `answer_delta`，包含 `message_id`、单调递增 `sequence`、`delta` 和 `node_name`。
3. 将 chunk 追加到本地列表。
4. 完成后拼成最终 `answer`，再执行 Memory write 和终态响应。

JSON 路径继续返回完整响应；不得为了流式展示调用第二次 LLM。终态 response 始终是权威结果。

### 4. AgentEvent 是公共事实事件，不承载隐藏推理

公共事件 contract 统一节点事件、Tool 事件和 `answer_delta`。`answer_delta` 只读取 OpenAI-compatible `delta.content`，忽略 `reasoning_content`。EventSink 异常不能改变 Agent 主流程。

V3.10.2 EventBus 继续负责 SSE 帧和终态关闭；V3.11 Skill 事件与公共 AgentEvent 共享同一队列，不再建立另一种文本流格式。

### 5. 前端使用乐观 assistant 消息并在终态对账

提交请求后立即创建空 assistant 消息。收到 `answer_delta` 时按 `message_id + sequence` 去重并追加；收到最终 response 后用完整 answer 覆盖文本并补齐 sources/run。若流中断，保留已收到文本并标记错误，不重复插入第二条 assistant 消息。

### 6. MCP 使用 Adapter 接入统一 Tool Registry

公共 Registry 只理解稳定 ToolDefinition、JSON arguments 和 ToolResult。V3.12 Adapter 负责把 `server::tool`、input schema、annotations 和 CallToolResult 映射到公共 contract。V3.12.1 只允许显式执行已注册的低风险 Tool，不新增 LLM 自动 Tool selection。

### 7. V3.12.1 提供独立教学入口

新增 `obsidian_rag/v3_12_1/`，通过 FastAPI JSON/SSE 和 CLI 展示 Core、Compatibility Adapter、Tool Registry 与答案流。它复用公共实现，不复制完整 Agent Graph；文档明确这是一轮架构迁移和传输体验改进。

## Risks / Trade-offs

- [迁移造成行为漂移] → 用现有 V3.9 cases、V3.10/V3.11 service/API 测试和响应快照做前后对照，不修改 Prompt 与检索参数。
- [SSE delta 与最终答案重复] → 前端只维护一个临时 assistant message，终态以完整 answer 覆盖。
- [并发请求共享 EventSink] → EventSink 必须是 request-scoped/context-local，不保存在进程级单例可变状态。
- [Provider 不支持 stream] → 自动回退 `complete()`；JSON 和终态 SSE 仍成功。
- [MCP 每次启动 stdio 进程较慢] → 保持 V3.12 短生命周期边界并记录耗时；Session Pool 留给生产化版本。
- [V3.12.1 范围较大] → 分为 Core parity、Tool Adapter、Streaming/UI 三个可独立验证的任务组。

## Migration Plan

1. 建立 Core contract 和从 V3.8.1 提升的稳定实现，运行行为对照测试。
2. 将 V3.10/V3.10.2/V3.11 依赖切换到 Core，保留原接口。
3. 接入 V3.12 MCP Tool Adapter，并保持显式执行边界。
4. 把 V3.10.3 streaming adapter 收敛为 Core Chat Client 能力，增加 `answer_delta`。
5. 更新 Agent Console 增量渲染，验证中断、回退和终态对账。
6. 发布独立 V3.12.1 API/CLI/文档；回滚时可将 dependencies 恢复到历史 Adapter，索引和 Memory 数据无需迁移。

## Open Questions

- 公共 Core 完成后，V3.10.3 Advanced Graph 是否立即改用 Core Chat Adapter，可在不影响 V3.12.1 完成标准的情况下后续迁移。
- MCP Session Pool 和跨进程 EventBus 仍需在生产部署前单独设计。
