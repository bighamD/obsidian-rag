## ADDED Requirements

### Requirement: 稳定 Conversation Thread
系统 SHALL 为每个 Conversation 持久保存稳定的 `thread_id`，并 MUST 为每次 `/ask` 创建独立的 `run_id`。同一 `conversation_id` 的后续请求 SHALL 使用相同 `thread_id` 调用 DeepAgents/LangGraph。

#### Scenario: 同一会话连续追问
- **WHEN** 同一 tenant、user 和 assistant 使用相同 `conversation_id` 发起第二次请求
- **THEN** 系统使用已有 `thread_id` 恢复先前 messages，并为本次请求生成新的 `run_id`

#### Scenario: 新会话不继承线程消息
- **WHEN** 相同用户使用新的 `conversation_id` 发起请求
- **THEN** 系统创建新的 `thread_id`，且不加载其他 Conversation 的线程 messages

### Requirement: 跨重启恢复
系统 SHALL 使用 PostgreSQL Checkpointer 持久保存线程 Agent State，使已完成消息和待审批中断在 API 服务重启后仍可恢复。

#### Scenario: 服务重启后继续对话
- **WHEN** 服务重启后用户使用原 `conversation_id` 再次提问
- **THEN** 系统从 Checkpointer 恢复该线程历史并继续生成与历史一致的回答

#### Scenario: 服务重启后恢复审批
- **WHEN** Tool Call 已进入 interrupt 且服务随后重启
- **THEN** 用户提交有效 resume decision 后系统从原 Checkpoint 继续，而不是重新执行已完成的副作用

### Requirement: Conversation Repository 独立职责
系统 SHALL 使用 Conversation Repository 保存会话列表所需的业务元数据，并 MUST NOT 将完整 Agent messages 复制为第二份消息事实来源。

#### Scenario: 查询会话列表
- **WHEN** 前端请求当前用户的 Conversation 列表
- **THEN** Repository 返回标题、状态、创建和更新时间等元数据，而无需扫描 Checkpoint 中的完整 messages

### Requirement: Thread Scope 隔离
系统 MUST 验证 `conversation_id` 所属的 tenant、user 和 assistant，禁止调用方仅凭 ID 恢复其他 scope 的线程。

#### Scenario: 跨用户访问 Conversation
- **WHEN** 用户 B 请求属于用户 A 的 `conversation_id`
- **THEN** 系统拒绝访问且不返回该线程 messages、Checkpoint 或运行信息

### Requirement: Conversation 删除边界
删除 Conversation SHALL 删除或失效其业务元数据和对应线程 Checkpoint；系统 MUST NOT 默认删除该用户跨线程共享的长期 Memory。

#### Scenario: 删除会话但保留偏好
- **WHEN** 用户删除一个 Conversation 后创建新 Conversation
- **THEN** 旧线程历史不可再恢复，但该用户明确保存的长期偏好仍可读取

