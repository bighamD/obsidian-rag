# Obsidian RAG 版本能力矩阵

本文是 `obsidian_rag/` 学习版本的统一导航，用于快速回答：

- 某个版本主要学习什么？
- 它相比上一版本新增了什么？
- 它明确不负责什么？
- 应该从哪个代码目录和 Guide 开始阅读？

版本号只表示学习演进顺序，不代表生产发布语义。完整路线和版本选择原因见 [Harness 学习路线](harness-learning-roadmap.md)，具体实现与断点见各版本 Guide。

## 当前主线

```text
V0-V2       RAG、Hybrid Retrieval、Evaluation
   ↓
V3-V3.8.1  Agent、Planner、Evidence、Context、Memory
   ↓
V3.9-V3.10.3 Evaluation、Production Runtime、Console、SSE、LangGraph Advanced
   ↓
V3.11.x     Skill、Docling、Chunking、Collection Router
   ↓
V3.12       MCP Protocol
   ↓
V3.12.1     AgentRuntime/Core + Unified ToolRegistry + Answer Streaming
   ↓
V3.12.2     Retrieval Reranking
   ↓
V3.12.3     MCP Agent Integration（已完成）
   ↓
V3.12.4     Unified Knowledge Routing（已完成）
   ↓
V3.13         Permission Policy（已完成）
   ↓
V3.14         Docker Sandbox Execution（已完成）
   ↓
V3.15         Recovery/HITL（已完成）
   ↓
V3.16         DeepAgents Tool Loop & Artifact（已完成）
   ↓
V3.17         DeepAgents Durable Memory & Context（已完成）
   ↓
V3.18         DeepAgents Production Customization（下一主线，计划中）
   ↓
V3.19         Production Hardening & Takeover Drill（计划中）
```

## 状态说明

| 状态 | 含义 |
| --- | --- |
| 已完成 | 代码和主要学习闭环已经落地 |
| 计划中 | 已进入 roadmap，但尚未实现 |
| 插入实验 | 为验证单项能力插入，不改变 Agent 主线 |
| 兼容入口 | 保留旧版 API/CLI 用于学习对照，不应继续承担公共核心职责 |

## Phase A：RAG 基础

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 入口 |
| --- | --- | --- | --- | --- |
| V0 | Local RAG | Markdown/PDF 加载、元数据、Chunk、Embedding、Qdrant、`search/ask` CLI | 无 FastAPI、无 Hybrid Retrieval、无 Agent | [根目录代码](../obsidian_rag) · [代码指南](obsidian-rag-code-guide.md) |
| V1 | Hybrid Retrieval API | FastAPI、Swagger、Dense + Keyword + RRF、统一 SearchHit、JSON Ask | 不做离线评估和 Agent 决策 | [代码](../obsidian_rag/v1) · [Guide](v1-hybrid-search-guide.md) |
| V2 | RAG Evaluation | Retrieval/Answer 数据集、Hit Rate、MRR、Source/Answer Coverage | 不改变检索和回答逻辑，只评估已有能力 | [代码](../obsidian_rag/v2) · [Guide](v2-evaluation-guide.md) |

## Phase B：Agent 主链路

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 入口 |
| --- | --- | --- | --- | --- |
| V3 | Rule Agent Loop | 规则版轻量 Agent、最多两次检索、trace | 不具备可靠 Intent Router；多跳判断仍是规则 | [代码](../obsidian_rag/v3) · [Guide](v3-agentic-rag-guide.md) |
| V3.1 | LLM Router | LLM 输出结构化 Router JSON，在 RAG 前决定 search/no_search/clarify | 不是原生 Tool Calling；代码仍解释 `action` | [代码](../obsidian_rag/v3_1) · [Guide](v3-1-llm-router-guide.md) |
| V3.2 | Tool Calling | 模型通过标准 `tool_calls` 选择 `search_notes/no_search/clarify` | 仍由 Harness 按 `tool.name` 分发；没有图编排 | [代码](../obsidian_rag/v3_2) · [Guide](v3-2-tool-calling-guide.md) |
| V3.3 | LangGraph Orchestration | `AgentState`、Node、Edge、条件路由，将 V3.2 流程图化 | 主要学习编排；没有 Planner 任务图 | [代码](../obsidian_rag/v3_3) · [Guide](v3-3-langgraph-guide.md) |
| V3.4 | Planner | LLM 把复杂目标拆成结构化 Plan JSON，并用 LangGraph 表达规划阶段 | 只生成 Plan，不执行检索和最终回答 | [代码](../obsidian_rag/v3_4) · [Guide](v3-4-planner-guide.md) |
| V3.5 | Planner Executor | 执行 Plan search steps、轻量 `ToolRegistry`、`StepResult`、答案综合 | Tool 仍以本地检索为主；无证据充分性判断 | [代码](../obsidian_rag/v3_5) · [Guide](v3-5-planner-executor-guide.md) |
| V3.6 | Evidence Checker | 检查计划步骤和检索证据覆盖，证据不足时补搜一次 | 不是离线评测器；只做单次运行中的证据判断 | [代码](../obsidian_rag/v3_6) · [Guide](v3-6-evidence-checker-guide.md) |
| V3.7 | Context Builder | 在 Answer 前选择、裁剪、排序和格式化 Memory/Chunk Context | 不持久化对话；`excluded_chunks` 仅用于观察 | [代码](../obsidian_rag/v3_7) · [Guide](v3-7-context-builder-guide.md) |
| V3.8 | Conversation Memory | 持久化原始 Turn，按 `memory_window` 加载最近对话 | 不压缩旧 Turn；窗口外内容暂不进入 Prompt | [代码](../obsidian_rag/v3_8) · [Guide](v3-8-conversation-memory-guide.md) |
| V3.8.1 | Memory Compaction | 最近 Turn 原文 + 旧 Turn 滚动摘要，控制对话 Context Window | 摘要不是新的用户 Turn；不做长期语义记忆检索 | [代码](../obsidian_rag/v3_8_1) · [Guide](v3-8-1-conversation-compaction-guide.md) |

## Phase C：评估与生产化

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 入口 |
| --- | --- | --- | --- | --- |
| V3.9 | Agent Evaluation Lite | 运行完整 Agent，再评估 routing、plan、tool、retrieval、evidence、answer | 是离线行为质检，不参与在线回答 | [代码](../obsidian_rag/v3_9) · [Guide](v3-9-agent-evaluation-guide.md) |
| V3.10 | Production Core | Production Run 生命周期、RunStore、错误摘要、Metrics、统一 Response 外壳 | 不是新的推理策略；RunStore 仍是进程内 | [代码](../obsidian_rag/v3_10) · [Guide](v3-10-production-core-guide.md) |
| V3.10.1 | Agent Console | Vite + Vue 3 会话界面，展示 Answer、Plan、Tool、Evidence、Context、Memory、Run | JSON first；最初没有真实节点实时事件 | [后端](../obsidian_rag/v3_10_1) · [Guide](v3-10-1-agent-console-guide.md) |
| V3.10.2 | Run Event Streaming | EventBus + SSE 推送节点、工具和最终响应，Console 实时更新 | 不展示隐藏 chain-of-thought；EventBus 不是分布式消息系统 | [代码](../obsidian_rag/v3_10_2) · [Guide](v3-10-2-run-event-streaming-guide.md) |
| V3.10.3 | LangGraph Advanced | Subgraph、`Send` 并行、`Command`、RetryPolicy、State History、messages stream | 插入实验；Checkpoint 仍是内存演示，不提供跨重启恢复 | [代码](../obsidian_rag/v3_10_3) · [Guide](v3-10-3-langgraph-advanced-patterns-guide.md) |

## Phase D：Skill 与知识库工程

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 入口 |
| --- | --- | --- | --- | --- |
| V3.11 | Skill System | Skill Registry、LLM Skill Router、选中后懒加载 `SKILL.md` 并注入 Planner | Skill 是方法上下文，不是 Tool；不执行 scripts/assets | [代码](../obsidian_rag/v3_11) · [Guide](v3-11-skill-system-guide.md) |
| V3.11.1 | Docling Ingestion | Docling 多格式解析、统一结构、HybridChunker、Adaptive Parent-Child 摄取 | 数据基础插入版本；不改变 Agent 决策 | [代码](../obsidian_rag/v3_11_1) · [Guide](v3-11-1-docling-structured-ingestion-guide.md) |
| V3.11.2 | Chunking Comparison | 对比 LangChain Parent、LlamaIndex Hierarchical、Semantic Splitter | Request-scoped 实验；不直接修改生产索引策略 | [代码](../obsidian_rag/v3_11_2) · [Guide](v3-11-2-chunking-framework-comparison-guide.md) |
| V3.11.3 | Collection Router | Knowledge Base Registry、LLM Collection Router、多库检索和跨库 RRF | 不做 ACL、多租户、Reranker 或完整 Agent 接入 | [代码](../obsidian_rag/v3_11_3) · [Guide](v3-11-3-collection-router-guide.md) |

## Phase E：MCP、公共 Core 与检索质量

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 入口 |
| --- | --- | --- | --- | --- |
| V3.12 | MCP Protocol Lab | 官方 MCP SDK、stdio、`initialize/tools/list/tools/call`、Demo/RAG MCP Server、结果适配 | 独立显式调用；每次调用使用短 Session，不进入完整 Agent | [代码](../obsidian_rag/v3_12) · [Guide](v3-12-mcp-integration-guide.md) |
| V3.12.1 | AgentRuntime/Core Extraction | 提升公共 Agent Core、统一 Local/MCP ToolRegistry、Answer Delta、TTFT、前端流式答案 | MCP Tool 仍以显式执行为主；不自动选择高风险 Tool | [代码](../obsidian_rag/v3_12_1) · [公共 Core](../obsidian_rag/core) · [Guide](v3-12-1-agent-core-streaming-guide.md) |
| V3.12.2 | Retrieval Reranking | RRF 扩大候选、CrossEncoder 重排 matched child、Parent Top K、fail-open 和排序评估 | 插入检索质量版本；不改变 Planner、Permission 或 Tool 决策 | [代码](../obsidian_rag/v3_12_2) · [共享 Reranker](../obsidian_rag/reranking) · [Guide](v3-12-2-retrieval-reranking-guide.md) |
| V3.12.3 | MCP Agent Integration | 配置化 Server Registry、stdio/Streamable HTTP、Session 复用、Tool Cache、Planner 自动选择只读 MCP Tool、Tool Observation | 不开放任意 Server、写入 Tool、Shell、Permission 或 Sandbox | [代码](../obsidian_rag/v3_12_3) · [Guide](v3-12-3-mcp-agent-integration-guide.md) |
| V3.12.4 | Unified Knowledge Routing | Core RetrievalScope、LLM Collection Router、自动/显式知识库范围、多库统一 Reranking、MCP Agent 与 Console 集成 | 不做 ACL、多租户、Permission、写入 Tool 或 Sandbox | [代码](../obsidian_rag/v3_12_4) · [Guide](v3-12-4-unified-knowledge-routing-guide.md) |

## Phase F：安全与恢复

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 状态 |
| --- | --- | --- | --- | --- |
| V3.13 | Permission Policy + Core Skill Integration | Principal、Tool allowlist、Schema 校验、风险等级、Collection scope、`allow/confirm/deny`；Core Skill 支持显式多选、`augment/exclusive`、Trigger/BM25 匹配和仅歧义时调用 LLM Router | `confirm` 暂不 interrupt/resume；Skill 不执行 scripts；不执行宿主机任意 Shell 或真实写入 | [代码](../obsidian_rag/v3_13) · [公共 Policy](../obsidian_rag/core/permissions) · [Core Skills](../obsidian_rag/core/skills) · [Guide](v3-13-permission-policy-guide.md) |
| V3.14 | Docker Sandbox Execution + Core Tool Agent 收敛 + Planner Collection Selection | 通用 Tool Catalog、执行和 Observation 提升到 Core；Planner 同次调用选择 search Collections；每 Run Workspace、Docker 隔离、资源限制和 Artifact 下载 | 不固定调用 LLM Collection Router；不开放宿主机任意 Shell；不实现 approval resume | [代码](../obsidian_rag/v3_14) · [Core Agent](../obsidian_rag/core/agent) · [Core Sandbox](../obsidian_rag/core/sandbox) · [Guide](v3-14-sandbox-execution-guide.md) |
| V3.15 | Recovery & HITL | 官方 LangGraph PostgresSaver、psycopg 连接池、interrupt/resume、PostgreSQL Run/Approval JSONB、allow/deny/edit、Tool 幂等和 Agent Console 审批 | 不做分布式队列、多人会签、复杂 RBAC 或跨 Run 业务幂等 | [代码](../obsidian_rag/v3_15) · [Guide](v3-15-recovery-hitl-guide.md) |

## Phase G：DeepAgents 生产迁移

| 版本 | 主题 | 核心职责与新增能力 | 明确边界 | 状态 |
| --- | --- | --- | --- | --- |
| V3.16 | DeepAgents Tool Loop & Artifact | 使用官方 `create_deep_agent`；适配 `search_notes`、Sandbox Backend、HITL、SSE 和 Artifact；跑通 `search -> ToolMessage -> write_file -> approval -> download` | 不做持久多轮 Memory、Skills、MCP、Sub-agent 或 Shell；不继续扩展自研 Planner 数据流 | 已完成 · [代码](../obsidian_rag/v3_16) · [Guide](v3-16-deepagents-tool-loop-guide.md) |
| V3.17 | DeepAgents Durable Memory & Context | 稳定 Thread、PostgreSQL Checkpointer、Conversation Repository、`CompositeBackend`、PostgresStore/`StoreBackend`、用户级长期 Memory、Offloading/Summarization、Policy 和 Audit | 不把全部 Turn 写成长记忆；不做复杂 Sub-agent、后台 consolidation 和跨历史向量检索 | 已完成 · [代码](../obsidian_rag/v3_17) · [Guide](v3-17-deepagents-durable-memory-context-guide.md) |
| V3.18 | DeepAgents Production Customization | 自定义 Middleware、Runtime Context、动态 Tool/Memory scope、Harness Profile、Sub-agent、确定性业务子图和后台 Memory consolidation | 不要求通用 Deep Agent Loop 代替严格事务/DAG；严格流程进入自定义 Sub-agent | 计划中 |
| V3.19 | Production Hardening & Takeover Drill | LangSmith Trace/Eval、超时取消重试、幂等、SSE replay、Secrets、租户隔离、部署、备份恢复和真实业务迁移 | 不再以单一概念 Demo 为目标，以生产 PR 和故障演练作为验收 | 计划中 |

## 能力反查

| 想学习的能力 | 首选版本 | 补充版本 |
| --- | --- | --- |
| Dense / Keyword / Hybrid / RRF | V1 | V3.11.3、V3.12.2 |
| Retrieval / Answer Evaluation | V2 | V3.9、V3.12.2 |
| Intent Router | V3.1 | V3.2、V3.3 |
| Tool Calling | V3.2 | V3.5、V3.12.1、V3.12.3、V3.16 DeepAgents Tool Loop |
| LangGraph 基础编排 | V3.3 | V3.4-V3.6 |
| LangGraph 高级能力 | V3.10.3 | V3.15 |
| Planner / Task Decomposition | V3.4 | V3.5、V3.12.3 |
| Tool Executor / Registry | V3.5 | V3.12.1 |
| Evidence Checker / Retry | V3.6 | V3.9 |
| Context Builder | V3.7 | V3.8.1、V3.12.3 |
| Conversation Memory | V3.8 | V3.8.1；V3.17 DeepAgents 持久线程 |
| Memory Compaction | V3.8.1 | V3.12.1 Core；V3.17 DeepAgents Summarization |
| Agent Evaluation | V3.9 | V2 |
| Run Lifecycle / Metrics | V3.10 | V3.10.2 |
| Agent Console | V3.10.1 | V3.10.2、V3.12.1 |
| SSE / Answer Streaming | V3.10.2 | V3.12.1 |
| Skill System | V3.11；V3.13 提升到 Core 主线并增加显式多选和条件 Router | V3.13 |
| Structured Ingestion / Parent-Child | V3.11.1 | V3.11.2、V3.12.2 |
| Multi-Collection Routing | V3.11.3 | V3.12.4 完整 Agent 集成 |
| MCP Protocol | V3.12 | V3.12.3 |
| Public Agent Core | V3.12.1 | V3.10、V3.11 |
| CrossEncoder Reranking | V3.12.2 | V1、V3.11.1 |
| Permission / Approval | V3.13 | V3.15 完整 interrupt/resume |
| Sandbox / Artifacts | V3.14 | V3.16 DeepAgents Backend Adapter |
| Checkpoint / HITL | V3.15 | V3.10.3、V3.16 `interrupt_on` |
| DeepAgents Harness / Middleware | V3.16 | V3.18 深度定制 |
| Observation-driven Tool Dataflow | V3.16 | V3.5 自研 Executor 对照 |
| DeepAgents Long-term Memory / StoreBackend | V3.17 | V3.8.1 自研 Memory 对照 |
| Runtime Context / Sub-agent | V3.18 | V3.10.3 LangGraph Subgraph |
| Production Reliability / Takeover | V3.19 | V3.9、V3.10、V3.15 |

## 最容易混淆的版本

| 对比 | 关键区别 |
| --- | --- |
| V2 vs V3.9 | V2 评估检索与答案；V3.9 评估完整 Agent 行为 |
| V3.1 vs V3.2 | V3.1 让 LLM 输出 Router JSON；V3.2 使用标准 tool_calls |
| V3.4 vs V3.5 | V3.4 只规划；V3.5 才执行 Plan |
| V3.6 vs V3.9 | V3.6 在线检查本次证据是否足够；V3.9 离线批量质检 Agent |
| V3.7 vs V3.8 | V3.7 组装本轮 Context；V3.8 持久化并读取跨轮 Memory |
| V3.10 Run vs V3.8 Memory | Run 描述一次执行；Memory 保存跨轮对话事实 |
| V3.10.2 trace vs chain-of-thought | trace 是可观察执行事实，不是模型隐藏推理 |
| V3.11 Skill vs Tool | Skill 提供方法；Tool 执行动作 |
| V3.12 MCP vs Tool Calling | MCP 定义发现/调用协议；Tool Calling 是模型的选择机制 |
| V3.12.1 vs V3.12.3 | V3.12.1 准备 Core 与统一 Registry；V3.12.3 才让完整 Agent 自动使用 MCP Tool |
| V3.12.2 Reranker vs RRF | RRF 按排名融合召回；Reranker 对 query-document 重新评分 |
| V3.11.3 vs V3.12.4 | V3.11.3 独立学习 Collection Router；V3.12.4 把它接入 Planner、Reranker、MCP、Context 和 Console |
| V3.13 Permission vs V3.14 Sandbox | Permission 决定能否执行；Sandbox 决定在哪里、以什么资源执行 |
| V3.13 confirm vs V3.15 HITL | V3.13 产生 confirm 并阻止执行；V3.15 才保存 Checkpoint、等待人工决定并 resume |
| Memory vs RunStore vs Checkpoint | Memory 延续跨轮对话；RunStore 展示一次运行生命周期；Checkpoint 保存 Graph 中间状态并驱动 resume |
| V3.15 Checkpoint vs V3.17 Memory | V3.15 的 Checkpoint 重点是恢复/HITL；V3.17 才系统处理同线程消息、跨线程 Store Memory 和 Context 生命周期 |
| 自研 Planner Executor vs V3.16 DeepAgents | 自研 Planner 预先生成步骤和参数；DeepAgents 每次读取 ToolMessage 后再决定下一次 Tool Call |
| V3.16 vs V3.17 | V3.16 先掌握 Tool Loop、HITL 和 Artifact；V3.17 才加入持久多轮会话和长期 Memory |

## 目录阅读建议

看到一个版本目录时，按以下顺序阅读：

1. 在本文确认版本主题和边界。
2. 阅读对应 Guide 的主流程图和“相比上一版本”章节。
3. 从该版本 `app.py`、`routes/` 找到 API 入口。
4. 沿 `dependencies.py -> service.py -> core/adapter` 阅读真实依赖。
5. 按 Guide 的断点表运行 `launch.json` 案例。
6. 最后阅读 `schemas.py`，确认请求、响应、State、Context、Trace 的边界。

## 维护规则

每次新增、插入、重命名或完成一个学习版本时，必须同步更新：

1. 本文对应版本行、状态和入口。
2. “当前主线”依赖顺序。
3. “能力反查”中的首选版本。
4. 容易产生混淆时，补充一条概念对比。
5. [Harness 学习路线](harness-learning-roadmap.md) 中的阶段状态。

本文只维护版本级导航，不复制 Guide 的 Swagger payload、完整断点表或实现细节。
