## Context

V3.16 通过 `deepagents.create_deep_agent` 建立了 Observation 驱动的 `model -> tools -> model` 循环，并复用 PostgreSQL Checkpointer 完成当前 Run 内的 `interrupt_on -> resume`。但是它在每次请求中生成新的 `run_id`，并把该值作为 LangGraph `thread_id`，因此 Checkpoint 只解决单次 Run 的恢复，不构成跨 `/ask` 的 Conversation Memory。

V3.17 需要同时处理四种生命周期不同的数据：同线程 messages、会话业务元数据、跨线程长期 Memory、接近模型窗口时生成的 Summary。它们不能继续混在一个 Turn 表、一个 JSON 响应或一个 Backend 路径中。该版本还必须保持 V3.16 的 Tool Loop、HITL、Sandbox Workspace、Artifact、JSON/SSE 和前端兼容投影不退化。

## Goals / Non-Goals

**Goals:**

- 使用稳定 `thread_id` 支持同一 Conversation 跨请求、跨服务重启继续对话。
- 使用多维 namespace 隔离并持久保存跨线程长期 Memory。
- 使用 DeepAgents/LangGraph 原生 Backend 与 Summarization 机制管理 Context 生命周期。
- 明确区分 Checkpoint、Conversation Repository、Long-term Store、Summary、Run 和 Artifact。
- 提供可查看、可更新、可删除、可审计的 Memory 管理能力。
- 保持 V3.16 的 Tool Loop、审批恢复和 Artifact 下载链路。

**Non-Goals:**

- 不把全部原始 Turn、完整 Answer、RAG chunk 或 Tool 输出自动复制到长期 Memory。
- 不实现跨全部历史会话的向量化语义检索。
- 不实现后台定时 Memory consolidation agent；首版使用 hot-path 明确写入。
- 不接入复杂 Sub-agent、Skills、MCP、Shell 或动态 Model Router。
- 不删除或重写旧 V3.8.1 Memory、V3.15 Checkpoint 和 V3.16 Adapter，它们继续作为原理对照。

## Decisions

### 1. `conversation_id` 稳定映射为 `thread_id`，`run_id` 只表示一次执行

请求必须携带或创建稳定的 `conversation_id`。V3.17 通过 Conversation Repository 解析其 `thread_id`，调用 DeepAgents 时传入：

```text
configurable.thread_id = conversation.thread_id
run_id                 = 本次请求的新执行标识
```

同一 Conversation 的多个 Run 共享 Checkpoint messages；不同 Conversation 即使属于同一用户也不共享线程消息。备选方案是继续使用 `run_id` 作为 `thread_id` 并手工拼接历史，但这会绕开 LangGraph Checkpoint 的状态恢复、HITL 和消息 reducer，因此不采用。

### 2. Conversation Repository 只保存业务元数据

Repository 保存 `conversation_id`、`thread_id`、tenant/user/assistant scope、标题、状态和时间戳。真实 Agent messages 由 PostgreSQL Checkpointer 保存，Repository 不复制完整消息。

这样前端可以高效查询会话列表，同时避免出现两套消息事实来源。删除 Conversation 时清理对应线程 Checkpoint 和会话元数据，但默认不删除同一用户的长期 Memory。

### 3. Checkpointer 与 Store 分别承载短期状态和长期 Memory

- PostgreSQL Checkpointer：同线程 messages、Agent State、HITL interrupt/resume。
- LangGraph Store：跨线程长期事实和偏好。
- Run Repository：一次执行的状态、响应和错误。
- Artifact Repository：生成文件及下载元数据。

Store namespace 至少使用 `(tenant_id, assistant_id, user_id)`，Memory key 使用稳定 UUID 或可更新的业务 key。禁止仅以 `user_id` 建 namespace，避免多租户串线。

### 4. 使用 Runtime Context 传递身份与能力范围

V3.17 定义显式 Runtime Context，至少包含：

```text
tenant_id
user_id
assistant_id
conversation_id
thread_id
principal / permission profile
```

Backend factory、Memory policy 和 Tool 构建过程只能从经过验证的 Runtime Context 获取 namespace，不接受模型生成的 tenant/user 参数。这样模型无法通过 Tool arguments 切换到其他用户的 Memory。

### 5. 使用 `CompositeBackend` 分离工作文件与持久 Memory

Backend 路由语义为：

```text
/memories/**  -> StoreBackend，按 Runtime namespace 持久化
其他路径       -> V3.16 兼容的线程工作 Backend / Sandbox Workspace
```

模型不能通过 `../`、绝对路径变体或 Symlink 绕过路由。工作文件继续遵守每 Run/Thread Workspace 和 Artifact 策略，长期 Memory 不作为 Artifact 下载。

### 6. 长期 Memory 采用受控的 hot-path 写入策略

首版允许保存稳定偏好、长期事实和用户确认后的决策。写入前由确定性 Policy 校验类型、scope、大小和敏感字段；高风险或不确定内容不自动持久化。每次 create/update/delete 都记录 Audit。

不采用“每轮结束后让模型总结整段对话并全部写入 Store”的方案，因为它会快速积累重复、错误和临时信息。后台去重、合并、冲突解决和 consolidation agent 留到 V3.18。

### 7. 使用模型 Profile 驱动的 Summarization/Offloading

V3.17 使用 DeepAgents `SummarizationMiddleware` 及其 Offloading 能力，在接近当前模型 Context Window 阈值时压缩较旧消息或大 Tool Result，而不是固定读取最近 N 轮或每四轮摘要。

Summary 必须尽量保留：当前目标、用户约束、已确认决定、未完成事项、Artifact 引用和继续执行所需的 Tool 结果。近期消息保留原文。响应中的 Summary/Context 字段仅用于调试观察，必须标明它们是否真正进入本次模型 Prompt，不能把兼容投影误称为精确 Wire Prompt。

### 8. API 和 Console 分层展示 Memory

V3.17 在 `/ask` JSON/SSE 响应中增加稳定的调试摘要，并增加 Conversation、Memory 和 Audit 管理接口。共享 Console 以独立区域展示：

```text
Thread History
Current Context
Context Summary
Long-term Memory
Memory Audit
Checkpoint / Run
```

旧后端缺少这些字段时前端保持兼容，不将其误报为整个 Console 不兼容。

### 9. V3.17 保持独立学习闭环

新增独立版本目录、FastAPI Swagger JSON/SSE、CLI、`launch.json`、带中文职责和 `Field(description=...)` 的 schemas、学习文档、断点表和至少三张 SVG。测试代码按仓库版本规范提供，但不采用 TDD、不默认执行耗时测试，也不自动启动 API 服务。

## Risks / Trade-offs

- [稳定 Thread 会不断积累 messages 和 Checkpoint 数据] → 使用 Summarization/Offloading、Conversation 删除和保留策略，并记录可观察的 token/summary 状态。
- [模型可能写入错误或短期 Memory] → 使用白名单类型、大小限制、显式 Policy、Audit 和 CRUD；复杂 consolidation 推迟到 V3.18。
- [Conversation、Checkpoint 与 Store 清理不一致] → Repository service 统一编排删除事务/补偿，并提供孤儿数据审计。
- [PostgreSQL 同时承载多类状态容易概念混淆] → 分表、分 repository、分 schema 响应，文档和 Console 明确数据所有者。
- [Summary 可能丢失细节] → 保留近期原始消息和关键状态字段，Summary 触发及内容可观察，并提供关闭/阈值配置用于调试对照。
- [不同 DeepAgents 版本的 Backend/Middleware API 有差异] → 封装薄 Adapter，业务层依赖本地 Protocol/Pydantic contract，不让 API schema 直接暴露框架内部类型。
- [跨租户 Memory 泄漏风险高] → namespace 只能由已验证 Runtime Context 构造，并增加隔离场景和 Audit 测试。

## Migration Plan

1. 新建 V3.17 schemas、Runtime Identity、Conversation Repository 和数据库迁移，不改变 V3.16。
2. 将 V3.16 Agent Adapter 复制/继承到 V3.17，拆分 `run_id` 与稳定 `thread_id`，验证同线程恢复和 HITL。
3. 接入 LangGraph Store、namespace resolver、`StoreBackend` 和 `CompositeBackend`，先提供显式 Memory CRUD。
4. 增加 Memory Policy、Agent hot-path 读写和 Audit，验证跨线程读取及跨用户隔离。
5. 接入 Summarization/Offloading 和 Context 调试投影，使用可调小阈值构造压缩案例。
6. 增加 FastAPI JSON/SSE、CLI、`launch.json`、Console 面板、文档、SVG 和断点表。
7. 更新 roadmap、版本能力矩阵和 `AGENTS.md` 当前主线状态。

回滚时停止 V3.17 并继续运行 V3.16。V3.17 使用独立路由和表/namespace，不迁移或删除 V3.16 Run、Checkpoint 和 Artifact 数据；如数据库迁移需要回退，先停止 V3.17 写入，再按 migration 顺序删除新增对象。

## Open Questions

- Conversation Repository 是否沿用当前 PostgreSQL 连接池还是抽象独立 repository factory，实施时以 V3.16 数据层现状和连接生命周期为准。
- DeepAgents 当前安装版本是否完整暴露 Summary 元数据；若框架不提供稳定字段，Console 只展示本地可验证的 summary event/metadata，不伪造精确 Prompt。
- 长期 Memory 写入首版采用受控文件 Tool 还是独立 `memory_put` Tool，将在确认 DeepAgents `StoreBackend` 的实际 Tool 暴露方式后选择；两种方式都必须经过同一 Policy 和 Audit。

## Implementation API Findings

- 当前安装版本为 `deepagents 0.6.12`。`create_deep_agent()` 已自动加入模型 Profile 驱动的 `SummarizationMiddleware`，V3.17 不重复安装第二个 Summary Middleware；调试阈值通过 `ChatOpenAI.profile.max_input_tokens` 配置模型 Profile。
- `StoreBackend` 在调用时通过 LangGraph `get_runtime()` 获取 Runtime Context，namespace callback 可以读取 `runtime.context`；V3.17 将把已验证的 identity 作为 `context=` 传给 `graph.stream()`。
- DeepAgents Summary 使用私有 `_summarization_event` 保存 `cutoff_index`、`summary_message` 和 `file_path`，原始 `messages` 不会被直接删除。V3.17 只投影这些可验证字段。
- Summary 默认把淘汰历史写入 `{artifacts_root}/conversation_history/{thread_id}.md`。V3.17 使用 `/context/` 的 Thread Store 路由保存该文件，避免每 Run Sandbox Workspace 导致下轮无法读取。
- 长期 Memory 采用独立 `remember_user_fact` / `forget_user_fact` Tool，Memory Service 同时维护 Store item 与 `/memories/profile.md`。DeepAgents `MemoryMiddleware` 只读取该 profile 文件，不允许模型直接决定 namespace。
