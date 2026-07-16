## Why

当前 Agent Console 把会话列表和标题保存在浏览器 `localStorage`，清理浏览器数据或换设备后即丢失，而且它可能与 MySQL 中真实存在的 Conversations/Turns 不一致。会话历史应以服务端持久化数据为事实来源，并提供能够一致删除 Conversation 及关联 Turns 的管理能力。

## What Changes

- 为公共 `console.v1` 增加服务端会话列表接口，返回会话标识、标题、Turn 数量和更新时间。
- 为公共 `console.v1` 增加删除会话接口；删除 Conversation 时由数据库事务和外键级联删除关联 Turns。
- 为 SQLite/MySQL Conversation Memory Store 增加一致的 list/delete 能力，便于契约测试和本地学习。
- Agent Console 启动后从 API 加载会话历史，不再把 `localStorage` 作为会话列表和消息的事实来源。
- 新建但尚未产生 Turn 的会话作为当前页面临时会话存在；首次回答落库后刷新服务端列表。
- 左侧会话列表增加删除操作；删除当前会话后自动选择下一条服务端会话，没有历史时创建一个临时新会话。
- 删除失败时保留当前 UI 状态并显示错误，不做乐观删除。
- 增加 Store、API、Vue composable 和组件交互测试，并更新 `console.v1` 文档。

## Capabilities

### New Capabilities

- `persistent-console-conversations`: 服务端会话列表、会话详情 hydration、Conversation/Turns 一致删除，以及以前端 API 数据为事实来源的会话管理流程。

### Modified Capabilities

- 无；`agent-console-contract-milestones` 变更尚未归档为公共基线，本次以新增 capability 描述增量行为。

## Impact

- 后端：`obsidian_rag/core/memory.py`、`obsidian_rag/core/mysql_memory.py`、`obsidian_rag/console_api/`。
- 前端：`production-client.ts`、`use-agent-console.ts`、`ConversationSidebar.vue`、相关类型和样式。
- 数据库：不新增表；使用现有 `turns.conversation_id -> conversations.conversation_id ON DELETE CASCADE`。
- API：新增 `GET /console/conversations` 和 `DELETE /console/conversations/{conversation_id}`；现有详情接口保持兼容。
- 数据迁移：MySQL 中已有会话自动出现在列表；浏览器旧 `localStorage` 不再作为历史来源。
- 非目标：不实现会话重命名、搜索、分页游标、多用户归属、软删除或恢复站。
