# V3.8.1 Conversation Compaction Guide

V3.8.1 的目标是在 V3.8 最近窗口 Memory 之上增加滚动会话摘要，让旧对话不会因为 `memory_window` 截断而永久退出 LLM 上下文。

## V3.8.1 比 V3.8 改进了什么

V3.8（历史实现）：

```text
SQLite 全部原始 Turns -> 最近 memory_window 轮 -> Planner / Answer
```

V3.8.1：

```text
MySQL 全部原始 Turns
  -> 旧 Turns 滚动摘要
  -> summary_text + 最近 memory_window 轮
  -> Planner / Answer
```

关键变化：

- LangGraph 新增 `compact_memory` 节点。
- MySQL `conversations` 增加滚动摘要状态。
- 旧 Turn 数量或估算 token 达到阈值时自动压缩。
- 支持 Swagger 和 CLI 手动强制压缩。
- Planner 和 Answer Context 同时接收 `summary_text` 与最近原始 Turns。
- 摘要失败时保留现有摘要和最近 Turns，不阻断本轮 RAG。
- `no_search` / `clarify` 不再直接把 Planner 的 `instruction` 当最终答案；在有 LLM 时会继续进入 Answer 节点，由通用 LLM 回答或发起澄清。

## 流程图

![V3.8.1 Conversation Compaction 流程](assets/rag-v3-8-1-conversation-compaction-flow.svg)

正常 graph path：

```text
load_memory
  -> compact_memory
  -> planner
  -> execute_steps
  -> evidence_check
  -> build_context
  -> synthesize_answer
  -> save_memory
```

`compact_memory` 不一定调用 LLM。没有旧 Turn 或未达到阈值时只返回跳过结果。

## 三层 Memory

| 层 | 保存内容 | 用途 |
| --- | --- | --- |
| Raw Turns | 全部原始用户问题、回答、sources、tool calls | 审计、查看、重新生成摘要。 |
| Rolling Summary | 最近一次压缩后的会话摘要 | 保留窗口之外的重要历史。 |
| Recent Turns | 最近 `memory_window` 轮原始对话 | 保留当前交流的准确措辞和指代。 |

最终 LLM Context 是：

```text
conversation_summary
+ recent_turns
+ current_question
+ retrieval_chunks
```

当计划是 `no_search` 或 `clarify` 时，`retrieval_chunks` 可以为空，但 Answer LLM 仍然会被调用：

```text
普通编程/知识问题 -> 通用回答，不添加知识库来源
实时天气/新闻问题 -> 说明当前没有外部实时工具，不编造事实
指代不明问题 -> 生成澄清问题
```

`used_retrieval=false` 只表示本轮没有调用 RAG，不表示本轮没有生成答案。

压缩不会删除 `turns`。摘要是可重新生成的派生数据，原始 Turn 才是事实来源。

## 自动压缩条件

V3.8.1 只检查“上次摘要截止点之后、最近窗口之前”的旧 Turns。

满足任一条件就触发：

```text
candidate_turn_count >= memory_compaction_trigger_turns
OR
estimated_input_tokens >= memory_compaction_trigger_tokens
```

默认值：

```json
{
  "memory_window": 3,
  "memory_compaction_enabled": true,
  "memory_compaction_trigger_turns": 4,
  "memory_compaction_trigger_tokens": 3000
}
```

滚动更新方式：

```text
新摘要 = 旧 summary_text + 新增待压缩 Turns
```

因此不会在每次压缩时重新读取全部历史。

## MySQL 结构

默认数据库：

```text
MySQL 数据库 `obsidian_rag`
```

可通过环境变量修改：

```text
RAG_MYSQL_HOST=127.0.0.1
RAG_MYSQL_PORT=3306
RAG_MYSQL_USER=root
RAG_MYSQL_PASSWORD=
RAG_MYSQL_DATABASE=obsidian_rag
```

`conversations` 新增：

| 字段 | 含义 |
| --- | --- |
| `summary_text` | 当前滚动摘要。 |
| `summary_through_turn_id` | 摘要已经覆盖到哪个 Turn。 |
| `summary_updated_at` | 最近摘要更新时间。 |

`turns` 仍保存完整原始数据，不因压缩删除记录。

## Swagger 用法

启动：

```bash
.venv/bin/uvicorn obsidian_rag.v3_8_1.app:app --host 127.0.0.1 --port 8011
```

打开：

```text
http://127.0.0.1:8011/docs
```

自动压缩问答：

```json
{
  "question": "那处理完厨房怎么清洁？",
  "conversation_id": "conv_compaction_demo",
  "memory_window": 3,
  "memory_compaction_enabled": true,
  "memory_compaction_trigger_turns": 4,
  "memory_compaction_trigger_tokens": 3000,
  "top_k": 5,
  "mode": "hybrid",
  "filters": null,
  "max_steps": 4,
  "max_retries": 1,
  "context_max_chunks": 4,
  "context_token_budget": 4000
}
```

手动压缩：

```text
POST /memory/conv_compaction_demo/compact
```

```json
{
  "keep_recent_turns": 1,
  "trigger_turns": 4,
  "trigger_tokens": 3000,
  "force": true
}
```

响应中的 `memory_compaction` 会说明是否尝试、是否成功、压缩了多少 Turns，以及摘要截止 Turn。

## CLI 用法

连续写入同一 conversation：

```bash
.venv/bin/obsidian-rag agent-v3-8-1 ask "生鸡肉要不要洗？" \
  --conversation-id conv_compaction_demo

.venv/bin/obsidian-rag agent-v3-8-1 ask "那处理完厨房怎么清洁？" \
  --conversation-id conv_compaction_demo
```

手动强制压缩：

```bash
.venv/bin/obsidian-rag agent-v3-8-1 compact conv_compaction_demo \
  --keep-recent-turns 1
```

## 核心流程断点调试

VS Code/Cursor 依次运行：

```text
V3.8.1 compaction: first turn
V3.8.1 compaction: follow-up turn
V3.8.1 compaction: force compact
```

按执行顺序设置断点：

| 顺序 | 断点 | 重点观察 |
| --- | --- | --- |
| 1 | `agent/service.py:78` `ask()` | request、conversation_id、initial_state。 |
| 2 | `agent/service.py:149` `_load_memory_node()` | 当前 summary 和最近 Turns。 |
| 3 | `agent/service.py:170` `_compact_memory_node()` | 是否进入 Compactor、压缩结果如何写回 AgentState。 |
| 4 | `compaction.py:26` `compact()` | candidate Turns、阈值判断、摘要 LLM messages。 |
| 5 | `memory.py:82` `load_compaction_candidate()` | 如何排除已摘要 Turns 和最近窗口。 |
| 6 | `memory.py:152` `save_summary()` | summary_text 和摘要截止 Turn 如何持久化。 |
| 7 | `context.py:98` `build_memory_aware_planner_question()` | summary + recent Turns 如何进入 Planner。 |
| 8 | `context.py:72` `_build_messages()` | summary + recent Turns + chunks 如何进入 Answer Context。 |
| 9 | `agent/service.py:403` `_synthesize_answer_node()` | 无论是否检索都观察 Answer LLM；无 LLM 时才观察非检索降级答案。 |
| 10 | `agent/service.py:434` `_save_memory_node()` | 当前原始问答仍然独立写入 turns。 |

关键分支：

```text
没有 candidate Turns -> 跳过压缩
未达到阈值 -> 跳过压缩
达到阈值 -> LLM 摘要 -> save_summary
摘要失败 -> 降级使用旧摘要 + 最近 Turns
```

行号会随代码变化；行号失效时以函数名重新定位。

## 文件职责

| 文件 | 作用 |
| --- | --- |
| `obsidian_rag/v3_8_1/schemas.py` | 定义压缩配置、结果和 API schema。 |
| `obsidian_rag/v3_8_1/memory.py` | 历史 SQLite Raw Turns 实现，保留用于迁移和旧测试。 |
| `obsidian_rag/v3_8_1/mysql_memory.py` | 当前 MySQL Raw Turns、摘要状态和候选 Turn 查询。 |
| `obsidian_rag/v3_8_1/compaction.py` | 阈值判断、摘要 Prompt、滚动摘要生成。 |
| `obsidian_rag/v3_8_1/context.py` | 将 summary 和最近 Turns 注入 Planner/Answer。 |
| `obsidian_rag/v3_8_1/agent/service.py` | V3.8.1 LangGraph 主流程。 |
| `obsidian_rag/v3_8_1/tools.py` | `search_notes` ToolRegistry。 |
| `obsidian_rag/v3_8_1/dependencies.py` | 构建 Retrieval、LLM、Memory Store 和 Compactor。 |
| `obsidian_rag/v3_8_1/routes/agent.py` | `POST /agent/ask`。 |
| `obsidian_rag/v3_8_1/routes/memory.py` | Memory 查看和手动压缩接口。 |
| `obsidian_rag/v3_8_1/app.py` | FastAPI app。 |

## 与 DeerFlow 的关系

本版参考 DeerFlow 的核心思想：

```text
旧消息摘要 + 最近消息原文 + 独立 summary state
```

但没有照搬 DeerFlow 的完整系统。当前不包含异步 Memory 队列、用户事实提取、置信度、过期检查、事实合并或跨 conversation 用户画像。

## 当前版本边界

V3.8.1 做：

- 会话内滚动摘要。
- token/Turn 双阈值触发。
- 保留最近原始 Turns。
- 保留所有 MySQL 原始记录。
- 手动和自动 Compaction。

V3.8.1 不做：

- 不做跨会话长期用户 Memory。
- 不做向量化 Memory 检索。
- 不做 LLM 提取用户偏好和稳定事实。
- 不做生产级异步摘要队列。

下一步仍可进入 V3.9 Agent Evaluation；更完整的 Selective Long-Term Memory 留到后续独立版本。
