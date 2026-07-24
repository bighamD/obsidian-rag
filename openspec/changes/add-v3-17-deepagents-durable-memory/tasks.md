## 1. 基线核对与版本骨架

- [x] 1.1 核对当前安装的 `deepagents`、`langgraph`、Checkpointer、Store、`CompositeBackend`、`StoreBackend` 和 `SummarizationMiddleware` 实际 API，并记录与 design 假设的差异
- [x] 1.2 阅读 V3.16 Agent、Runtime、Repository、Backend、routes 和 schemas，确定可复用 Adapter 与必须隔离的 V3.17 代码边界
- [x] 1.3 新建 `obsidian_rag/v3_17/` 主流工程目录、模块入口和版本常量，保持 V3.16 对外行为不变
- [x] 1.4 定义 V3.17 request/response、Runtime Identity、Conversation、Memory、Summary、Context 和 Audit schemas，为职责和关键字段补充中文 `Field(description=...)`

## 2. PostgreSQL 数据模型与 Repository

- [x] 2.1 设计并增加 V3.17 Conversation、Memory Audit 及必要 Store metadata 的数据库 migration，保持 Checkpoint、Run 和 Artifact 表职责独立
- [x] 2.2 实现 Conversation Repository 的创建、scope 查询、列表、详情、标题/状态更新和删除
- [x] 2.3 实现 `conversation_id -> stable thread_id` 映射，并保证 `run_id` 每次请求独立生成
- [x] 2.4 实现 Conversation 删除编排：清理线程 Checkpoint 和会话元数据，但默认保留用户级长期 Memory
- [x] 2.5 实现 Memory Audit Repository，记录 create/update/delete、Summary 和清理事件的 actor、scope、Run 与安全摘要

## 3. Durable Thread 与 Checkpoint 恢复

- [x] 3.1 将 V3.17 DeepAgents 调用配置改为稳定 `thread_id`，不再使用 `run_id` 作为 Conversation Thread
- [x] 3.2 验证同一 Conversation 多次 `/ask` 恢复 Checkpoint messages，新 Conversation 不继承线程 messages
- [x] 3.3 保持 V3.16 `interrupt_on -> resume`、副作用幂等和服务重启后的 HITL 恢复语义
- [x] 3.4 增加 tenant/user/assistant 对 Conversation ownership 的确定性校验，拒绝跨 scope Thread 访问
- [x] 3.5 在响应和 SSE 事件中明确返回 `conversation_id`、`thread_id` 和 `run_id`，并保持终态一致

## 4. Long-term Memory Store 与 Backend

- [x] 4.1 实现 Runtime Context 和 namespace resolver，使用 `(tenant_id, assistant_id, user_id)` 构造不可由模型覆盖的 Memory scope
- [x] 4.2 初始化并注入持久 LangGraph Store，封装 V3.17 本地 Store Adapter 和生命周期管理
- [x] 4.3 接入 DeepAgents `StoreBackend`，实现长期 Memory 的读取、创建、更新和删除
- [x] 4.4 使用 `CompositeBackend` 将 `/memories/**` 路由到 StoreBackend，将普通工作文件路由到 V3.16 兼容工作 Backend
- [x] 4.5 保留 V3.16 Workspace 路径保护、Sandbox、Artifact 注册和下载能力，并防止路径变体绕过 Memory/Workspace 路由
- [x] 4.6 实现 Memory Policy，限制可保存类型、内容大小、敏感字段和默认禁止项
- [x] 4.7 将 Agent hot-path Memory 读写接入 Tool Loop，并为每次变更写入 Audit

## 5. Context Window、Summary 与 Offloading

- [x] 5.1 建立模型 Context Profile，配置窗口大小、Summary/Offloading 触发阈值和调试覆盖参数
- [x] 5.2 接入 DeepAgents `SummarizationMiddleware`，根据 token/模型窗口而非固定轮数触发摘要
- [x] 5.3 接入大 Tool Result Offloading，保留可恢复引用、关键证据和必要摘要
- [x] 5.4 构造并验证 Summary 保留当前目标、用户约束、确认决定、未完成事项、Artifact 和关键 Tool Observation
- [x] 5.5 实现 Context 调试投影，明确标注 Thread History、Summary、Long-term Memory、RAG chunks、当前 Prompt Context 与兼容字段的区别
- [x] 5.6 发布不含隐藏 chain-of-thought 的 Summary/Offloading SSE 事件和 token/触发统计

## 6. V3.17 Agent 与 Runtime 集成

- [x] 6.1 基于 V3.16 创建 V3.17 AgentService，注入 Conversation Repository、Checkpointer、Store、CompositeBackend、Memory Policy 和 Runtime Context
- [x] 6.2 保持 `search_notes -> ToolMessage -> write_file -> approval -> Sandbox -> Artifact` 主链路可用
- [x] 6.3 实现首轮、同 Conversation 追问、新 Conversation 读取长期偏好和 Summary 后继续任务的响应组装
- [x] 6.4 保持 JSON、SSE、resume 和 recover 的状态转换一致，确保 Memory/Context 阶段事件按执行时机实时发布
- [x] 6.5 对 Store、Summary、Checkpoint 和 Repository 异常增加安全错误边界，避免单一观察字段失败导致整个 Answer 500

## 7. FastAPI、CLI 与调试入口

- [x] 7.1 新增 V3.17 FastAPI app、dependencies 和 `/ask` JSON/SSE、resume、recover routes，不使用端口 `8021`
- [x] 7.2 增加 Conversation 列表/详情/删除、Memory CRUD 和 Memory Audit Swagger 接口及可直接运行的 payload
- [x] 7.3 增加 `obsidian-rag agent-v3-17` CLI，支持首轮、追问、长期 Memory 和 Summary 调试参数
- [x] 7.4 更新 `.vscode/launch.json`，提供 V3.17 API、首轮、同 `conversation_id` 追问、新 Conversation 长期 Memory 和低阈值 Summary 案例
- [x] 7.5 增加 service、API、CLI、scope 隔离、HITL 恢复和 Summary 行为的测试代码，但不默认运行耗时测试或自动启动服务

## 8. Agent Console

- [x] 8.1 扩展共享 Console API types 和 capability detection，兼容 V3.17 与旧版后端
- [x] 8.2 增加 Thread History、Current Context、Context Summary、Long-term Memory、Memory Audit 和 Checkpoint/Run 分区
- [x] 8.3 增加 Memory 查看、编辑和删除交互，并清楚展示 namespace、来源 Run 和生命周期
- [x] 8.4 验证切换 Conversation 后右侧 Memory/Context 面板可从服务端恢复，不依赖浏览器临时内存
- [x] 8.5 验证连接 V3.16 或更早后端时只隐藏不支持的面板，不误报整个 Console 不兼容

## 9. 学习文档与图解

- [x] 9.1 编写 V3.17 Guide，说明相比 V3.16 的改进、版本边界、文件职责、数据表职责和 Swagger payload
- [x] 9.2 绘制端到端 Durable Memory 主流程 SVG，展示 `/ask -> Conversation -> Checkpoint -> Store -> DeepAgents -> Summary -> Response`
- [x] 9.3 绘制 Checkpoint、Conversation Repository、Long-term Store、Summary、Run 和 Artifact 生命周期对比 SVG
- [x] 9.4 绘制同 Thread 追问、跨 Thread 长期 Memory、Context Summary 三条路径的时序/分支 SVG
- [x] 9.5 整理核心断点调试表，按真实执行顺序列出当前文件行号、函数和关键变量，并覆盖正常、隔离拒绝、Summary、HITL 和删除分支
- [x] 9.6 更新 `docs/harness-learning-roadmap.md`、`docs/version-capability-matrix.md` 和 `AGENTS.md`，将 V3.17 标记为已完成并明确 V3.18 下一主线

## 10. 完成校验

- [x] 10.1 使用 XML 工具校验所有 SVG，并核对图中字段、存储层和真实代码行为一致
- [x] 10.2 核对所有 V3.17 Pydantic 对外关键字段均有中文描述，Swagger 能区分原始消息、Summary、长期 Memory 和调试投影
- [x] 10.3 使用静态检查和轻量手工请求验证首轮、同 Thread 追问、跨 Thread Memory、跨用户拒绝、Summary、approval resume 和 Artifact 链路；除非用户明确要求，不运行 `pytest`
- [x] 10.4 确认未自动启动 Swagger/API 服务、未占用 `8021`，并整理按代码、前端、文档合理拆分的中文 commit 建议
