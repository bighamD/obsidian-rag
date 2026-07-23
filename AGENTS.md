@RTK.md

# AGENTS.md

# 禁用superpowers skill（十分重要， 仅在用户明确要求才启用）

## 默认沟通

- 默认用中文回答。
- 命令、文件名、配置项、API 名称保留英文原文。
- 解释学习概念时优先结合本仓库已有版本：`v0`、`v1`、`v2`、`v3`、`v3_1`、`v3_2`、`v3_3`、`v3_4`、`v3_5`、`v3_6`、`v3_7`、`v3_8`、`v3_8_1`、`v3_9`、`v3_10`、`v3_10_1`、`v3_10_2`、`v3_10_3`、`v3_11`、`v3_12`、`v3_13`。

## 本地端口约束

- `8021` 已被本机系统服务占用，后续新增版本、API、CLI、前端代理、测试示例、文档和 `launch.json` 禁止使用该端口。
- 调整版本端口时，必须同步检查后端启动配置、CLI 默认 `--api-base`、前端 `VITE_API_TARGET`、测试示例和文档地址，避免共享前端因端口不一致误报 Console 不兼容。

## 提交习惯

- 提交或 push 前默认不运行 `pytest`、测试用例或其他耗时验证；只有用户明确要求时才执行。

## 新增版本的固定要求

每次新增一个学习版本时，保持独立版本目录和完整学习闭环。

整体学习路线应该大致吻合：

```text
docs/harness-learning-roadmap.md
```

新增版本前先检查 roadmap 当前阶段。若实现内容需要偏离 roadmap，必须在对应版本文档里说明偏离原因、取舍和下一步如何回到主线。

每次新增、插入、重命名或完成一个学习版本时，必须同步更新 `docs/version-capability-matrix.md` 的版本行、当前主线、能力反查、依赖关系和状态；该文档是版本职责与能力边界的统一入口。

必须包含：

- 独立目录，例如 `obsidian_rag/v3_5/`。
- FastAPI app，Swagger 可测试 JSON 接口。
- 新版本的 `schemas.py` 必须为 Pydantic 模型添加职责注释；输入、输出、Memory、Context、Trace 等对外关键字段必须使用 `Field(description=...)` 提供中文说明，使 Swagger/OpenAPI 可直接解释字段。涉及 LLM Context 时，必须明确区分原始 Turn、滚动摘要、知识库 chunk、实际 Prompt 字段与仅用于调试的响应字段。
- CLI 调试入口，例如 `obsidian-rag agent-v3-5 ...`。
- VS Code/Cursor `launch.json` 调试配置。
- 单元测试，至少覆盖 service、API、CLI。
- 学习文档，说明新版本比上一版本改进了什么。
- SVG 图解至少 2 张，常规版本应提供 3 张：必须包含主流程图，并根据版本重点补充阶段分工/概念对比、数据或 Top K 变化、状态分支、Parent-Child 关系、时序等教学图解；不得只是同一流程的重复排版。
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
- 实施或修改版本后不要自动启动 Swagger/API 服务，由用户自主启动和调试；除非用户明确要求启动服务。

## 版本边界

新增版本必须说清楚：

- 当前版本做什么。
- 当前版本不做什么。
- 相比上一版本新增了什么能力。
- 下一版本大概率会补什么能力。

如果某个版本只是 planner、router、eval 或其他局部能力，不要偷偷接入完整 RAG 流程。必须在文档和图里明确边界。

## 文档图片风格

后续新增版本的 SVG 视觉风格优先参考 V3.12.2：

```text
docs/assets/rag-v3-12-2-reranking-flow.svg
docs/assets/rag-v3-12-2-rrf-vs-reranker.svg
docs/assets/rag-v3-12-2-top-k-funnel.svg
docs/assets/rag-v3-12-2-parent-child-rerank.svg
```

旧版布局可辅助参考：

```text
docs/assets/rag-v3-4-planner-flow.svg
```

统一要求：

- 每个新增学习版本至少提供 2 张 SVG，常规版本应提供 3 张；复杂版本可以更多。
- 至少包含一张端到端主流程图；其余图应分别解释最容易混淆的概念、关键数据变化或条件分支。
- 使用深蓝渐变背景、圆角卡片、轻阴影、蓝/绿主强调色和黄/紫辅助强调色，保持与 V3.12.2 图解一致的视觉语言。
- 图中文字默认使用中文，类名、API、配置项和算法名称保留英文；标题应直接说明图的教学目的。
- 同一张图只表达一个核心问题，避免把完整代码、过长段落或所有分支塞进一张图。
- SVG 必须包含 `role="img"`、`title` 和 `desc`，保证基本可访问性。
- 学习文档应把 SVG 嵌入到对应概念章节附近，而不是只在文末放链接；文末可额外提供 SVG 图解索引。
- 完成前使用 XML/SVG 校验工具检查格式，并核对图中的数量、阶段名称和代码实际行为一致。

## 当前版本学习路线

已完成到：

```text
V3.15 Recovery & HITL
```

V3.12 在 V3.11 Skill System 之后增加标准化外部工具协议：

```text
FastAPI / CLI -> McpClientManager -> initialize -> tools/list -> tools/call
              -> Demo MCP Server / RAG MCP Server
              -> McpToolDefinition / McpToolCallResponse
```

V3.12 已完成：

- 使用官方 Python `mcp` SDK 和 `stdio` Transport。
- 实现 `initialize`、`tools/list`、`tools/call` 和短生命周期 `ClientSession`。
- 提供低风险 Demo MCP Server，以及暴露 `search_notes`、`list_collections` 的 RAG MCP Server。
- 将远端 Tool Schema 和 Call Result 适配为稳定的本地 Pydantic 契约。
- 提供独立 `obsidian_rag/v3_12/`、FastAPI Swagger JSON、CLI 和 `launch.json`。
- 补充学习文档、文件职责、Swagger payload、条件分支、断点说明和 SVG 流程图。

V3.12 仍然不做：

- 不让 LLM 自动选择 MCP Tool，当前先显式调用。
- 不执行 Skill `scripts/`，不开放 Shell 或任意文件写入。
- 不实现 Permission Policy、Sandbox、MCP resources/prompts 或生产级 Session Pool。

V3.12.1 已完成：

- 将稳定 Agent schemas、Planner、Context、Memory、Compaction、Tool Registry 和 AgentService 提升到 `obsidian_rag/core/`。
- V3.10、V3.10.2、V3.11 当前主线不再直接依赖 V3.8.1 AgentService/schemas。
- 本地 Tool 与 V3.12 MCP Tool 通过统一 Registry 被发现和显式执行。
- 最终 Answer 支持安全的 `answer_delta`、TTFT/生成耗时与非流式回退，不展示 `reasoning_content`。
- Agent Console 在单个 assistant 气泡中增量展示，并在终态补齐 sources、Run 和 Memory。
- 提供独立 `obsidian_rag/v3_12_1/`、FastAPI JSON/SSE、CLI、测试、文档、SVG 和断点配置。

V3.12.1 仍然不做：

- 不改变 Prompt、检索、Evidence 或 Memory 语义。
- 不实现 fast path、Permission、Sandbox、Shell、MCP Session Pool 或自动高风险 Tool 选择。

V3.12.2 已完成：

- 在 Hybrid/RRF 召回后增加可插拔 CrossEncoder Reranking。
- 支持 matched child 重排、Parent Top K、fail-open 和排序评估。

V3.12.3 已完成：

- 使用 YAML 配置 MCP Server Registry，支持 `stdio` 与 `streamable_http`。
- 通过 FastAPI lifespan 和每 Server Worker Task 持有、复用并关闭 MCP Session。
- 将 MCP Tool Catalog 提供给 Planner，完整 Agent 可生成并执行通用 `tool` step。
- 将 MCP Tool Result 适配为独立 Tool Observation，进入 Context、Answer、Trace、Memory 和 Agent Console。
- 继续复用 V3.12.2 Reranking；本地 `search_notes` 不通过 MCP 绕回自身。

V3.12.3 仍然不做：

- 不开放请求动态配置任意 MCP Server。
- 不开放写入 Tool、Shell、Skill scripts、Permission、审批或 Sandbox。

V3.12.4 已完成：

- 将 `RetrievalScope`、Resolver Protocol、Knowledge Base Registry 和 LLM Collection Router 提升到 `obsidian_rag/core/collections/`。
- 仅在注入 Resolver 时为 Core Agent Graph 增加 `resolve_retrieval_scope` 节点，旧版本路径保持兼容。
- 将 V3.11.3 Collection Router 与 V3.12.2 `search_collections()` 结合，执行多库候选融合和全局 Reranking。
- 保留 V3.12.3 MCP Tool Selection、持久 Session、Tool Observation、JSON/SSE 和共享 Agent Console。
- 前端支持 Auto Collection、Router 开关、最大知识库数和 RetrievalScope 观察面板。

V3.12.4 仍然不做：

- 不为每个 search subquery 重复路由，当前每个 Agent Run 只解析一次全局知识库范围。
- 不实现 Collection ACL、多租户授权、Permission Policy、写入 Tool 或 Sandbox。

V3.13 已完成：

- 在 V3.12.4 完整链路中增加可选 `authorize_steps` Core Graph Node。
- 提供统一 Principal、Tool allowlist、required permission、Collection scope、JSON Schema 和风险等级检查。
- Local `search_notes`、MCP Tool、retry search 与显式 MCP call 统一经过 `allow/confirm/deny` Policy。
- `confirm` 和 `deny` 返回结构化 StepResult，不调用 Tool，也不让 Agent 500。
- PermissionReport 进入 Context、Trace、Audit、JSON/SSE 和共享 Agent Console。
- 将 V3.11 Skill Registry、条件 LLM Skill Router 和按需加载提升到 `obsidian_rag/core/skills/`，并在 Planner 前接入同一个 Core AgentState。
- Core Skill 路由支持显式单/多 Skill、`augment/exclusive`、Trigger/BM25/词项覆盖率候选匹配，以及 `need_llm_skill_router()` 灰区升级策略。
- 共享 Console 支持输入 `/` 选择显式 Skills，并展示候选分数、显式/隐式来源、Router 是否调用和全部加载摘要。
- 提供独立 `obsidian_rag/v3_13/`、FastAPI、CLI、测试代码、Guide、SVG 和断点配置。

V3.13 仍然不做：

- `confirm` 暂不执行 LangGraph interrupt/resume，真正人工审批恢复进入 V3.13.1 或 V3.15。
- 不开放真实文件写入、宿主机 Shell、Sandbox、多租户认证或持久化审计数据库。
- 不执行 Skill `scripts/` 或 `assets/`，Skill 仍然只是 Planner 方法上下文。

V3.14 已完成：

- 生产主线由 Planner 在同一次调用中为 search step 选择 Collections，`search_notes` 负责 Registry、上限和实际检索校验；不再固定调用独立 LLM Collection Router。
- 新增 `obsidian_rag/core/sandbox/`，使用短生命周期 Docker Container 提供真实隔离。
- 每个 Agent Run 使用独立 Workspace，拒绝绝对路径、目录逃逸和 Symlink 穿透。
- 提供 `sandbox::read_file`、`write_file`、`list_files`、`run_command`，所有调用继续经过 V3.13 Policy。
- 默认关闭网络，使用只读根文件系统、`cap-drop=ALL`、`no-new-privileges`、CPU/内存/PID/超时和输出限制。
- 生成文件登记为 Artifact，进入 JSON/SSE、下载接口和共享 Agent Console。
- Docker 不可用时返回 unavailable，不降级成宿主机 Shell。

V3.14 仍然不做：

- 不开放 `bash -c`、`sh -c`、宿主机任意 Shell 或项目目录写入。
- 不执行 Skill `scripts/`，不实现 Container Pool、多租户调度或持久 Artifact 元数据数据库。
- 不实现 `confirm → interrupt → resume`，该能力进入 V3.15。

V3.10.3 和 V3.11.1-V3.11.3 是已完成的扩展学习版本，不改变当前主线。下一阶段建议：

```text
V3.15 Recovery & HITL（已完成）
```

V3.15 已完成：

- 使用 LangGraph 官方 `PostgresSaver` 持久保存 Graph Checkpoint。
- 在 Permission 与 Tool Executor 之间增加 `approval_gate`，`confirm` 触发 `interrupt()`。
- 支持 `allow`、`deny`、`edit` 和 `Command(resume=...)`。
- Run 增加 `waiting_for_approval`，审批、Run 和 Tool 幂等结果使用 PostgreSQL `JSONB` 持久化。
- V3.15 PostgreSQL 使用 psycopg ConnectionPool；Conversation Memory 继续使用 MySQL。
- 成功副作用 Tool 使用持久幂等结果，避免节点恢复时重复执行。
- 共享 Agent Console 支持审批参数查看、编辑、允许和拒绝。

V3.15 仍然不做：

- 不实现分布式队列、多人会签、复杂 RBAC、审批超时或生产级灾备。
- 不保证跨 Run 的业务幂等，不把 Conversation Memory、Run Store 与 Checkpoint 合并。

## CodeGraph

In repositories indexed by CodeGraph (a `.codegraph/` directory exists at the repo root), reach for it BEFORE grep/find or reading files when you need to understand or locate code:

- **MCP tool** (when available): `codegraph_explore` answers most code questions in one call — the relevant symbols' verbatim source plus the call paths between them, including dynamic-dispatch hops grep can't follow. Name a file or symbol in the query to read its current line-numbered source. If it's listed but deferred, load it by name via tool search.
- **Shell** (always works): `codegraph explore "<symbol names or question>"` prints the same output.

If there is no `.codegraph/` directory, skip CodeGraph entirely — indexing is the user's decision.
