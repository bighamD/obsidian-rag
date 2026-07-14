# MySQL Conversation Memory 迁移说明

## 当前状态

当前 V3.10.2 服务的 Conversation Memory 已从 SQLite 切换到本机 MySQL：

```text
AgentService -> MySQLConversationMemoryStore -> MySQL 8.4
                                      -> obsidian_rag.conversations
                                      -> obsidian_rag.turns
```

SQLite `.rag/v3_10_memory.sqlite3` 已迁移 12 个 `conversation` 和 19 条 `turn`。原文件保留作为迁移前备份，不再作为运行时读写源。

## 连接配置

`.env` 使用以下配置：

```dotenv
RAG_MYSQL_HOST=127.0.0.1
RAG_MYSQL_PORT=3306
RAG_MYSQL_USER=root
RAG_MYSQL_PASSWORD=
RAG_MYSQL_DATABASE=obsidian_rag
```

MySQL 数据库和表会在 `MySQLConversationMemoryStore` 首次初始化时自动创建。Sequel Ace 可以使用：

```text
Host: 127.0.0.1
Port: 3306
Username: root
Password: 留空
Database: obsidian_rag
```

主要查看两张表：

| 表 | 内容 |
| --- | --- |
| `conversations` | 会话时间、滚动摘要、摘要覆盖到哪条 Turn。 |
| `turns` | 原始用户问题、助手回答、来源 JSON、工具调用 JSON。 |

`turns.sequence_id` 替代了 SQLite 的 `rowid`，用于保证 `memory_window` 和 compaction 的顺序判断。

## 重新执行迁移

迁移脚本默认迁移当前 V3.10 SQLite 文件：

```bash
.venv/bin/python scripts/migrate_sqlite_memory_to_mysql.py
```

也可以指定其他 SQLite 文件：

```bash
.venv/bin/python scripts/migrate_sqlite_memory_to_mysql.py .rag/v3_8_1_memory.sqlite3
```

脚本按 `conversation_id` 和 `turn_id` 幂等写入，重复执行不会创建重复 Turn。旧版本 SQLite 文件不自动合并，因为不同学习版本可能存在相同的 `conversation_id`；需要迁移时应明确指定文件并先确认数据边界。

## 运行验证

启动当前服务后，打开：

```text
http://127.0.0.1:8014/docs
```

通过 `GET /console/conversations/{conversation_id}?window=3` 查看 MySQL 中的最近 Turn，或在 Sequel Ace 中直接查看 `turns` 表。

当前没有把 `RunRecord` 迁移到 MySQL；`InMemoryRunStore` 仍然只保存当前进程内的 Run 观测数据。
