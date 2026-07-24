## ADDED Requirements

### Requirement: Memory 与 Conversation 管理 API
V3.17 SHALL 提供 Conversation 列表/详情/删除、长期 Memory CRUD 和 Memory Audit 查询接口，所有接口 MUST 按 Runtime Principal 和 scope 授权。

#### Scenario: Swagger 管理 Memory
- **WHEN** 用户在 Swagger 使用有效 tenant、user 和 assistant scope 调用 Memory API
- **THEN** 系统返回结构化 JSON，并通过字段描述解释 Thread、Store、Summary 和 Audit 的区别

### Requirement: JSON 与 SSE 状态一致
V3.17 的 JSON、SSE、CLI 和 Console SHALL 对同一 Run 返回一致的 `conversation_id`、`thread_id`、`run_id`、Memory operation、Summary 状态和终态响应。

#### Scenario: SSE 完成后补齐终态
- **WHEN** 前端通过 SSE 观察一次包含 Memory 读取或写入的 Run
- **THEN** 流事件实时展示可公开的阶段状态，终态响应补齐与 JSON 接口一致的 Memory 和 Context 摘要

### Requirement: Memory 生命周期审计
系统 SHALL 记录 Conversation 创建/删除、Checkpoint 清理、长期 Memory 变更和 Summary 触发的可审计事件，并 SHALL 提供关联 `run_id`、`conversation_id` 和 actor 的查询能力。

#### Scenario: 排查错误记忆来源
- **WHEN** 管理员按 memory key 查询 Audit
- **THEN** 系统返回该 Memory 的创建、修改和删除链路以及关联 Run，但不返回未授权内容

### Requirement: 兼容旧版 Console
共享 Agent Console SHALL 识别 V3.17 capability 字段，并 MUST 在连接 V3.16 或更早后端时隐藏不支持的 Memory/Context 面板，而不是将整个后端判定为不兼容。

#### Scenario: 切换 V3.16 后端
- **WHEN** Console 从 V3.17 切换到只提供 V3.16 response 的 API
- **THEN** 对话、Tool、Approval 和 Artifact 功能继续可用，V3.17 专属面板显示为不可用或隐藏

### Requirement: V3.17 独立学习闭环
V3.17 SHALL 提供独立目录、FastAPI Swagger JSON/SSE、CLI、`launch.json` 调试案例、带中文职责和 `Field(description=...)` 的 Pydantic schemas、学习文档、文件职责、核心断点表和至少三张 SVG。文档 MUST 覆盖同线程追问、跨线程长期 Memory、跨用户隔离、Summary 触发、HITL resume 和删除边界。

#### Scenario: 完整学习案例
- **WHEN** 用户按文档依次执行首轮、同 Conversation 追问、新 Conversation 长期 Memory 读取和 Summary 压缩案例
- **THEN** 用户能够从 Swagger、数据库、断点和 Console 对照解释各类状态由谁保存及何时进入模型 Context

#### Scenario: 服务启动约束
- **WHEN** V3.17 实施完成
- **THEN** 项目提供可运行配置但不自动启动 Swagger/API 服务，且不使用已占用的 `8021` 端口
