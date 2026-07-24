## ADDED Requirements

### Requirement: 多维 Memory Namespace
系统 MUST 使用至少包含 `tenant_id`、`assistant_id` 和 `user_id` 的 namespace 保存长期 Memory，namespace MUST 由已验证的 Runtime Context 构造而不是由模型 Tool arguments 决定。

#### Scenario: 相同用户跨 Conversation 读取 Memory
- **WHEN** 相同 tenant、assistant 和 user 在新 Conversation 中提问
- **THEN** 系统能够读取该 namespace 中已确认保存的长期 Memory

#### Scenario: 跨租户隔离
- **WHEN** 两个 tenant 使用相同 `user_id`
- **THEN** 两者的长期 Memory 完全隔离且查询结果不互相可见

### Requirement: 长期 Memory 内容策略
系统 SHALL 只允许稳定偏好、长期事实和确认后的决策作为默认长期 Memory 类型，并 MUST NOT 默认保存普通寒暄、临时问题、完整模型回答、RAG chunks 或冗长 Tool 输出。

#### Scenario: 保存稳定用户偏好
- **WHEN** 用户明确表示“以后回答控制在 100 字以内”且写入通过 Policy
- **THEN** 系统保存该偏好，并允许同 scope 的新 Conversation 使用它

#### Scenario: 临时问题不进入长期 Memory
- **WHEN** 用户只询问一次“今天天气怎么样”且未明确要求记住
- **THEN** 系统不把该问题或完整回答写入长期 Memory

### Requirement: Persistent Store Backend
系统 SHALL 使用 LangGraph Store 与 DeepAgents `StoreBackend` 持久保存长期 Memory，并 SHALL 通过 `CompositeBackend` 将 `/memories/` 与普通工作文件路由到不同 Backend。

#### Scenario: Memory 与工作文件分离
- **WHEN** Agent 分别写入 `/memories/preferences.md` 和普通工作文件
- **THEN** 前者进入用户长期 Store namespace，后者进入线程工作 Backend，二者具有不同生命周期

### Requirement: Memory CRUD
系统 SHALL 提供按当前授权 scope 查询、创建、更新和删除长期 Memory 的 API，并 MUST 校验 schema、内容大小和类型。

#### Scenario: 用户删除错误 Memory
- **WHEN** 用户通过 Memory API 删除当前 scope 下的一条错误事实
- **THEN** 后续 Conversation 不再读取该事实，同时保留删除 Audit

### Requirement: Memory 写入审计
每次长期 Memory create、update、delete SHALL 记录 actor、scope、operation、memory key、时间、来源 Run 和安全内容摘要；Audit MUST NOT 暴露 Secret 或其他用户内容。

#### Scenario: 查看 Memory 来源
- **WHEN** 用户或管理员查看一条长期 Memory 的审计记录
- **THEN** 系统能够说明它由哪个 Run、何种操作和何时产生或修改

