# AGENTS.md

## 默认沟通

- 默认用中文回答。
- 命令、文件名、配置项、API 名称保留英文原文。
- 解释学习概念时优先结合本仓库已有版本：`v0`、`v1`、`v2`、`v3`、`v3_1`、`v3_2`、`v3_3`、`v3_4`、`v3_5`、`v3_6`、`v3_7`、`v3_8`、`v3_8_1`、`v3_9`、`v3_10`。

## 提交习惯

- 提交或 push 前默认不运行 `pytest`、测试用例或其他耗时验证；只有用户明确要求时才执行。

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
- 新版本的 `schemas.py` 必须为 Pydantic 模型添加职责注释；输入、输出、Memory、Context、Trace 等对外关键字段必须使用 `Field(description=...)` 提供中文说明，使 Swagger/OpenAPI 可直接解释字段。涉及 LLM Context 时，必须明确区分原始 Turn、滚动摘要、知识库 chunk、实际 Prompt 字段与仅用于调试的响应字段。
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
V3.10 Production Core
```

当前 V3.10 在 V3.8.1 Agent 外增加单次运行的生命周期与可观测层：

```text
ProductionAskRequest -> RunRecord(queued/running) -> V3.8.1 AgentService.ask()
                     -> succeeded: metrics / tool summary / token estimate
                     -> failed: standardized error
```

V3.10 会：

- 复用 V3.8.1 的完整 Agent 链路，不修改 Planner、Tool、Memory 或 Prompt。
- 创建独立 `prod_...` Run ID，并保留 V3.8.1 的 `agent_run_id`。
- 返回生命周期事件、总耗时、graph/trace 数、工具聚合、检索结果数和可观察 Answer token 估算。
- 将异常标准化为 `RunError`，不返回 Python traceback。
- 通过进程内 `InMemoryRunStore` 支持 `GET /runs` 与 `GET /runs/{run_id}` 查询。
- 使用 `.rag/v3_10_memory.sqlite3` 隔离 V3.10 调试产生的 Raw Turns。

V3.10 仍然不做：

- 不持久化 Run，也不做跨进程运行查询、队列或 dashboard。
- 不提供供应商真实 token / 成本数据，也不做自动重试。
- 不改变 V3.8.1 的推理和执行策略。

下一阶段建议：

```text
V3.11 Skill System
```

V3.11 将学习 Skill Registry、Skill Router 和按需加载 `SKILL.md`，让 Agent 先决定采用哪一种任务方法。

## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.

@RTK.md
