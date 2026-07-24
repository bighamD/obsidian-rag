## Why

V3.16 已经跑通 DeepAgents 的 Tool Loop、HITL 和 Artifact，但每次 `/ask` 仍以新的 `run_id` 作为 `thread_id`，相同会话无法在多次请求或服务重启后继续。V3.17 需要对齐真实 Harness 工程和即将接手的生产任务，建立持久多轮会话、用户级长期 Memory 与可控的 Context Window 生命周期。

## What Changes

- 新增独立的 `obsidian_rag/v3_17/`，复用 V3.16 Tool Loop、Sandbox Backend、HITL、Artifact、JSON/SSE 和共享 Agent Console。
- 将稳定的 `conversation_id` 映射为 DeepAgents/LangGraph `thread_id`，使用 PostgreSQL Checkpointer 保存并恢复同线程 messages 和中断状态。
- 增加 Conversation Repository，持久保存会话元数据、标题、创建时间、更新时间和业务状态，但不复制 Graph messages。
- 接入 LangGraph Store 与 DeepAgents `StoreBackend`，按照 `tenant_id`、`assistant_id`、`user_id` 隔离跨线程长期 Memory。
- 使用 `CompositeBackend` 将 `/memories/` 路由到持久 Store，其他工作文件继续保留在线程级 State/Sandbox Backend。
- 增加长期 Memory 写入策略，只允许稳定偏好、长期事实和确认后的决策进入长期存储；临时问题、完整回答和 RAG chunks 默认不写入。
- 使用 DeepAgents Offloading/Summarization 管理长会话，不再使用固定 `memory_window` 或固定轮数压缩规则。
- 增加 Conversation、Memory 和 Audit 的查询、更新、删除接口，并在 Swagger 和 Console 中区分 Thread History、Long-term Memory、Summary、Current Context、Checkpoint 和 Run。
- 补充 CLI、`launch.json` 调试案例、学习文档、核心断点表和 SVG 图解；不自动启动 Swagger 服务。

## Capabilities

### New Capabilities

- `durable-conversation-threads`: 使用稳定 Thread 和 PostgreSQL Checkpointer，在多次请求及服务重启后恢复同一会话的 Agent messages、HITL 和执行状态。
- `scoped-long-term-memory`: 使用 LangGraph Store、`StoreBackend` 和多维 namespace 保存、读取、更新和删除跨线程长期 Memory，并防止跨租户或跨用户串线。
- `managed-context-window`: 使用 DeepAgents Offloading/Summarization 对长会话上下文进行压缩和卸载，同时保留近期消息、关键目标、决定、Artifact 与必要工具结果。
- `memory-observability-governance`: 提供 Conversation Repository、Memory Policy、Audit 和 API/Console 观察能力，明确各种状态的来源、生命周期和可删除边界。

### Modified Capabilities

无。当前 `openspec/specs/` 没有需要修改的既有 capability；V3.17 作为新的生产迁移学习版本增加独立能力规范。

## Impact

- 新增 `obsidian_rag/v3_17/`、对应 FastAPI routes、Pydantic schemas、dependencies、CLI 和调试配置。
- 复用并适配 `obsidian_rag/v3_16/` 的 DeepAgents Agent、Runtime、Repository、Sandbox Backend 和响应投影。
- PostgreSQL 将同时承载 Checkpoint、Conversation metadata、Long-term Store 数据和 Memory Audit；各表及职责必须保持分离。
- 请求契约新增或明确 `tenant_id`、`user_id`、`assistant_id`、`conversation_id`，响应契约增加 Thread、Summary、Long-term Memory 和 Context 调试信息。
- 共享 Agent Console 增加 Memory/Context 观察与管理面板，同时保持对旧后端版本的兼容判断。
- 可能新增或启用 DeepAgents/LangGraph Store、Backend 与 Summarization 相关依赖，但不引入向量化历史搜索、复杂 Sub-agent 或后台 consolidation agent。
