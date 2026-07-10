# AGENTS.md

## 默认沟通

- 默认用中文回答。
- 命令、文件名、配置项、API 名称保留英文原文。
- 解释学习概念时优先结合本仓库已有版本：`v0`、`v1`、`v2`、`v3`、`v3_1`、`v3_2`、`v3_3`、`v3_4`、`v3_5`、`v3_6`、`v3_7`、`v3_8`、`v3_8_1`。

## 新增版本的固定要求

每次新增一个学习版本时，保持独立版本目录和完整学习闭环。

整体学习路线应该大致吻合：

```text
docs/harness-learning-roadmap.md
```

新增版本前先检查 roadmap 当前阶段。若实现内容需要偏离 roadmap，必须在对应版本文档里说明偏离原因、取舍和下一步如何回到主线。

必须包含：

- 独立目录，例如 `obsidian_rag/v3_5/`。
- FastAPI app，Swagger 可测试 JSON 接口。
- CLI 调试入口，例如 `obsidian-rag agent-v3-5 ...`。
- VS Code/Cursor `launch.json` 调试配置。
- 单元测试，至少覆盖 service、API、CLI。
- 学习文档，说明新版本比上一版本改进了什么。
- SVG 流程图，帮助理解当前版本主流程。
- 文件职责说明，解释新增目录里每个文件的作用。
- 核心流程断点调试说明，按真实执行顺序列出主链路。
- 断点表必须包含当前文件行号、函数名和每一步需要观察的关键变量。
- 文档必须说明正常主链路和条件分支，例如 retry、clarify、no_search。
- `launch.json` 必须提供可直接运行的调试案例；涉及 Memory 时至少提供首轮和同一 `conversation_id` 的追问案例。
- 文档中的断点行号必须在版本完成前按当前代码核对；同时注明代码变化后应以函数名重新定位。

默认接口要求：

- 当前优先返回 JSON response。
- 暂不默认实现 SSE，除非用户明确要求。
- Swagger payload 要在文档中给出可直接测试的示例。

## 版本边界

新增版本必须说清楚：

- 当前版本做什么。
- 当前版本不做什么。
- 相比上一版本新增了什么能力。
- 下一版本大概率会补什么能力。

如果某个版本只是 planner、router、eval 或其他局部能力，不要偷偷接入完整 RAG 流程。必须在文档和图里明确边界。

## 文档图片风格

后续 SVG 图优先参考：

```text
docs/assets/rag-v3-4-planner-flow.svg
```

## 当前版本学习路线

已完成到：

```text
V3.8.1 Conversation Compaction
```

当前 V3.8.1 在 V3.8 的 Memory read/write 中间增加滚动摘要：

```text
load_memory -> compact_memory -> planner -> execute_steps -> evidence_check -> retry_search -> evidence_check -> build_context -> synthesize_answer -> save_memory
```

V3.8.1 会执行 RAG：

- 调用 `RetrievalService.search()`。
- 支持 dense / keyword / hybrid retrieval。
- 返回 `conversation_id`、`memory_snapshot`、`memory_compaction`、`memory_write`、`context_bundle`、`trace`。
- 当某个 search step 没有证据时，最多按 `max_retries` 补搜。
- SQLite 保存完整原始 turns，并额外保存滚动 `summary_text` 和摘要截止 Turn。
- ContextBuilder 注入滚动摘要和最近 `memory_window` 轮原文。
- 旧 Turn 数量或估算 token 达到阈值时自动压缩，也支持 Swagger/CLI 手动压缩。
- 摘要失败时降级使用已有摘要和最近 Turns，不阻断 RAG。

V3.8.1 仍然不做：

- 不做向量化 Memory 检索和跨 conversation 用户画像。
- 不做异步事实提取、事实置信度、过期检查和 Memory consolidation。
- 不做生产级权限审批和 shell execution。

下一阶段建议：

```text
V3.9 Agent Evaluation
```

V3.9 再评估 Router、Planner、Tool、Memory、Evidence 和 Answer 的行为是否符合预期。

## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
