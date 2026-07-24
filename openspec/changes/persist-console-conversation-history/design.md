## Context

MySQL 已经持久化 `conversations` 和 `turns`，并通过 `ON DELETE CASCADE` 建立关联，但公共 Memory Store 只暴露单个 snapshot 的读写能力。前端因此自行在 `localStorage` 维护会话列表、标题和部分消息，形成了浏览器状态与数据库状态两个事实来源。

本次需要同时扩展 Store、`console.v1`、Vue composable 和侧栏交互。会话列表属于 Console 产品视图，不改变 Agent 运行时使用的 Memory Window；聊天历史 hydration 与 Planner Memory Window 也需要避免继续混为同一参数。

## Goals / Non-Goals

**Goals:**

- MySQL 成为已持久化会话列表的唯一事实来源。
- 提供按最近更新时间排序的服务端会话摘要列表。
- 在一个数据库事务中删除 Conversation 及关联 Turns。
- 保持未发送消息的新会话可以立即在前端使用。
- 删除当前会话后提供确定、无空指针的选择行为。
- 保持 `console.v1` 向后兼容，只新增接口和可选能力字段。

**Non-Goals:**

- 不实现会话重命名、全文搜索、分页游标或多用户权限。
- 不把 Run Store 与 Conversation 一起删除；当前 Run Store 是进程内调试数据，不是 Conversation 子资源。
- 不修改 Agent Memory Window、Compaction 或写入时机。
- 不将空白临时会话提前写入 MySQL。

## Decisions

### 1. Store 暴露 list/delete 领域方法

SQLite 和 MySQL Store 都增加：

- `list_conversations(limit)`：返回 `ConversationSummary`。
- `delete_conversation(conversation_id)`：返回删除结果和关联 Turn 数。

`ConversationSummary.title` 使用第一条 Turn 的用户问题生成，避免新增 title 列和迁移。标题在 Store 公共 helper 中统一截断；`updated_at` 使用 Conversation 每次 append 时已有的更新时间。

备选方案是在 `conversations` 新增 title 列，但标题仍来源于首问，会引入不必要的数据迁移和双写。

### 2. 删除在 Store 事务边界内完成

MySQL 先读取 Turn 数量，再删除 Conversation，依赖现有 `ON DELETE CASCADE` 删除 Turns；整个过程复用 `_session()` 的 commit/rollback。SQLite 因历史表没有启用可靠级联，显式先删 Turns 再删 Conversation，但仍位于同一个连接事务内。

不存在的 Conversation 返回 `deleted=false`，API 转换为 404，防止前端把未发生的删除视为成功。

### 3. Console API 新增集合和删除资源操作

- `GET /console/conversations?limit=50` 返回 `ConsoleConversationListResponse`。
- `DELETE /console/conversations/{conversation_id}` 返回 `ConsoleConversationDeleteResponse`。
- `GET /console/conversations/{conversation_id}` 继续负责 hydration。

`/console/config` 增加 list/delete endpoint 和 `conversation_management=true`。这是 `console.v1` 的向后兼容扩展，不升级到 `console.v2`。

### 4. 前端服务端会话与临时会话使用一个 view model

`ConsoleSession` 增加 `persisted`。API list 映射为 `persisted=true`，新建按钮创建的会话为 `persisted=false`。前端不再读写 `localStorage` 会话数组。

启动顺序：

```text
config -> health + runs + conversation list -> select first or create temporary -> hydrate selected
```

首次 Agent 成功写入 Memory 后重新请求会话列表，并保留当前 `conversation_id`，使临时会话转为持久化会话。

### 5. 聊天显示窗口与 Agent Memory Window 分离

前端 hydration 固定请求最近 20 条 Turn，用于聊天显示；提交 Agent 时仍使用运行参数中的 `memoryWindow`。这样用户把 Memory Window 设置为 0 或 1 时不会导致历史聊天区域同时消失。

### 6. 删除交互保持 props down / events up

`ConversationSidebar.vue` 只接收 sessions 和 deleting ID，通过 `delete` 事件上报。删除按钮使用 `stop` 防止同时触发 select，并提供 `aria-label`。是否调用 API、如何切换会话和错误处理全部留在 composable。

删除按钮直接向 composable 发出删除动作，不增加二次确认。按钮通过 title 明确说明持久化会话会同时删除关联 Turns，并在请求运行中或已有删除请求时禁用，避免重复操作。

## Risks / Trade-offs

- [硬删除不可恢复] → 当前学习阶段明确为硬删除，并在按钮文案和 API 文档标注会级联删除 Turns。
- [首问包含很长文本] → 标题统一压缩到 28 个字符并保留省略号。
- [旧 SQLite 外键未级联] → SQLite Store 显式删除 Turns，测试直接验证孤儿记录不存在。
- [首次回答结束后列表刷新失败] → 当前聊天仍保留，错误只影响侧栏刷新；下次刷新工作区可恢复。
- [同时删除和运行同一会话] → 前端在 `isRunning` 时禁用删除；本版不实现跨客户端并发锁。

## Migration Plan

1. 增加 Store summary/delete 数据结构和 SQLite/MySQL 实现。
2. 增加 Console list/delete schema、routes 和 manifest capability。
3. 增加 Store/API 测试，使用 SQLite 测试事务结果并用真实 MySQL 做只读列表验证。
4. 前端增加 API 类型和 client 方法，移除 localStorage 会话读写。
5. 重构 composable 启动、刷新、提交后同步和删除状态机。
6. 更新侧栏删除 UI、测试和文档。

回滚时可恢复前端 localStorage 逻辑并移除新增路由；数据库结构未变化，无需回滚迁移。

## Open Questions

- 后续是否增加软删除和恢复站：留到真正面向生产用户时评估。
- 是否独立提供分页 Turns API：当前最多 20 条足够学习使用，长会话在后续分页版本处理。
