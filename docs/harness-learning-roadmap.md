# Harness Engineering Learning Roadmap

这份计划书接在 V3.3 之后，用来系统学习真实 harness / agent 工程的架构。当前项目已经完成了从固定 RAG 到 LangGraph Agentic RAG 的基础链路，后续重点不再是“多加几个接口”，而是理解 harness 工程里每一层为什么存在、解决什么问题。

## 当前基线

已完成的学习链路：

```text
V3    ：规则版 agent loop
V3.1  ：LLM Router，显式 intent routing
V3.2  ：Tool Calling，模型通过 tool_calls 选择工具
V3.3  ：LangGraph，用 State + Node + Edge 编排流程
V3.4  ：LangGraph Planner，把复杂问题拆成 Plan JSON
V3.5  ：Planner Executor，执行 search steps 并综合答案
V3.6  ：Evidence Checker，检查证据覆盖并触发一次补搜
V3.7  ：Context Builder，选择、裁剪并格式化本轮上下文
V3.8  ：Conversation Memory，SQLite 持久化并加载最近对话窗口
V3.8.1：Conversation Compaction，旧 Turns 滚动摘要 + 最近 Turns 原文
V3.9  ：Agent Evaluation Lite，运行 Agent 并用结构化契约评测行为
V3.10 ：Production Core，为单次 Agent Run 提供生命周期、观测和错误摘要
V3.10.1：Agent Console，Vite + Vue 3 消费 JSON Run / Agent Response
V3.10.2：Run Event Streaming，复用 Agent Console 消费 SSE 运行事件
V3.10.3：LangGraph Advanced Patterns，学习子图、并行、状态历史与消息流（已完成）
V3.11：Skill System，Skill Registry、LLM Skill Router 和渐进式加载
V3.12：MCP Integration，MCP Client/Server、tools/list、tools/call 和 Tool Adapter（已完成）
V3.12.1：AgentRuntime/Core Extraction，把成熟 Agent 内核、MCP Adapter 和 answer_delta 提升到无版本号公共运行时（已完成）
V3.12.2：Retrieval Reranking，在 RRF 与 ContextBuilder 之间增加可插拔 CrossEncoder、fail-open 和离线排序评估（已完成）
V3.12.3：MCP Agent Integration，配置化连接、Session 复用、Planner 自动选择只读 MCP Tool 和 Tool Observation（已完成）
V3.12.4：Unified Knowledge Routing，把 Collection Router、多库 Reranking 与 MCP Agent 合并为完整主链路（已完成）
V3.13：Permission Policy，统一 Tool allowlist、权限、scope、Schema、风险等级和执行审计；同时把 V3.11 Skill Router 提升到 Core 并接回完整主链（已完成静态策略版）
V3.14：Sandbox Execution，Docker 隔离执行、每 Run Workspace、资源限制和 Artifacts（已完成）
V3.15：Recovery & HITL，PostgreSQL 持久 Checkpoint、interrupt/resume、人工审批和 Tool 幂等（已完成）
```

当前工程已经包含 intent router 能力：

- V3.1 是显式 router：模型输出 `RouterDecision JSON`。
- V3.2/V3.3 是隐式 router：模型通过 `tool_calls` 选择 `search_notes`、`no_search`、`clarify`。

V3.9 已建立 Agent 行为回归基线；V3.10 已把运行生命周期、观测和错误摘要系统化；V3.10.1/V3.10.2 已补齐 Agent Console 和 SSE 运行事件；V3.11 已学习 Skill 方法选择；V3.12 已补 MCP Client/Server 和标准工具协议。

## 总体学习路线

```text
Phase 0：复盘当前 Agentic RAG 基础
Phase 1：Planner，复杂任务拆解
Phase 2：Executor，按计划执行工具步骤
Phase 3：Evidence Checker，证据覆盖与重试
Phase 4：Context Builder，组装可控上下文
Phase 5：Memory，对话窗口、滚动摘要和长期记忆边界
Phase 6：Agent Evaluation，评估 router/tool/planner/answer
Phase 7：Production Core，Run Lifecycle、配置、观测和稳定性
Phase 7.1：Agent Console，消费 JSON Run / Agent Response 的会话与运行详情界面
Phase 7.2：Run Event Streaming，SSE 推送真实节点、工具和最终完成事件
Phase 7.3：LangGraph Advanced Patterns，子图、并行执行、恢复和消息流
Phase 8：Skill System，Skill Registry、Skill Router 和渐进式加载
Phase 9：MCP Integration，连接外部 MCP 并暴露本地 RAG 能力
Phase 9.1：AgentRuntime/Core Extraction，解除生产主线对 V3.8.1 学习目录的长期依赖
Phase 9.2：Retrieval Reranking，在 ContextBuilder 前增加可插拔相关性重排
Phase 9.3：MCP Agent Integration，让完整 Agent 通过生产形态连接并执行只读 MCP Tool
Phase 9.4：Unified Knowledge Routing，在 search step 前解析知识库范围并执行多库统一重排
Phase 10：Permission Policy，工具风险分级、参数校验和人工审批
Phase 11：Sandbox Execution，隔离执行、资源限制和 Artifacts
Phase 12：Recovery & HITL，Checkpoint、恢复和人工介入
```

## Harness 模块映射

附件里的总结可以作为后续学习路线的总框架：

```text
AI Agent = LLM + Harness
```

其中 LLM 负责思考、生成、推理、规划；Harness 负责让模型行为变成可控的软件流程。后续版本会逐步覆盖图里的核心模块，但不会一次性塞进一个版本。

| Harness 模块 | 本项目对应版本 | 当前状态 |
| --- | --- | --- |
| Context / 上下文 | V3.7、V3.8.1 | V3.7 独立 `ContextBuilder`；V3.8.1 加入滚动摘要和最近对话。 |
| Tool Calling / 工具调用 | V3.2、V3.3、V3.5 | 已覆盖：模型选择工具、LangGraph 编排、`ToolRegistry` 执行工具。 |
| Skills / 技能系统 | V3.11；V3.13 Core 增强 | 已覆盖：Skill Registry、显式单/多 Skill、Trigger/BM25 候选匹配、条件 LLM Skill Router、按需加载多个 `SKILL.md`。 |
| MCP / 外部工具协议 | V3.12、V3.12.3 | V3.12 覆盖协议与 Server；V3.12.3 已补配置化连接、Session 复用和完整 Agent 自动选择。 |
| File I/O / 文件读写 | V0、V1 | 已覆盖基础：Markdown/PDF loader、chunk、ingest。后续不作为 agent 主线重点。 |
| Shell Execution / 终端执行 | V3.14 Sandbox Execution | 后期只在隔离 Sandbox 中开放，不直接把宿主机 Shell 暴露给模型。 |
| Permissions / 权限审批 | V3.13 Permission Policy | 在 Sandbox 前补工具白名单、风险等级、参数校验、scope 和人工审批。 |
| Memory & State / 记忆状态 | V3.3、V3.5、V3.8、V3.8.1 | 已有 AgentState、MySQL Raw Turns、最近窗口和滚动摘要。 |
| Orchestrator / 任务编排 | V3.3、V3.4、V3.5、V3.6、V3.10.3 | V3.3-V3.6 学习基础 node/edge 和条件分支；V3.10.3 补充子图、并行、动态路由和恢复模式。 |
| Verification / 测试验证 | V2、V3.6、V3.9 | V2 是 retrieval/answer eval；V3.6 是运行时 evidence check；V3.9 Lite 用 case contract 评测 routing、plan、tool、retrieval、evidence 和 answer。 |
| Observation / 返回观察 | V3.5、V3.6、V3.10 | 已有 `trace`、`step_results`；V3.10 已补 `RunRecord`、latency、tool summary、token estimate 和 error summary。 |
| Agent Console / 前端观察 | V3.10.1、V3.10.2 | V3.10.1 消费 JSON 响应；V3.10.2 已通过 SSE 接收运行中事件。 |
| AgentRuntime / Core | V3.12.1、V3.12.4 | 已提升稳定 Agent 内核；V3.12.4 增加 RetrievalScope 契约、Resolver Protocol 和可选 Graph Node。 |
| Reporter / 汇总输出 | V3.5、V3.7 | 已有 `synthesize_answer`；V3.7 会把上下文构建从 reporter 中拆出去。 |
| Checkpoint / 恢复 | V3.10.3、V3.15 | V3.10.3 用 `InMemorySaver` 学习 State History；V3.15 再补持久恢复、interrupt/resume、幂等和 Human-in-the-loop。 |

这张图里的模块都会涉及，但节奏上分两类：

- 主线必学：`Context`、`Tool Calling`、`Memory & State`、`Orchestrator`、`Verification`、`Observation`、`Reporter`。
- 后期或可选：`Permissions`、`Shell Execution`、更完整的 `File I/O`。这些更偏生产安全和通用 agent 平台，不适合太早压进当前 RAG 学习线。

当前到 V3.12.4 为止，项目已经覆盖了：

```text
Memory Reader -> Planner -> Orchestrator -> Tool Executor -> Evidence Checker -> Context Builder -> Reporter -> Memory Writer
                                                              -> Agent Evaluation -> Production Run Observation -> Agent Console
```

还缺的关键层是：

```text
Permission Policy
Sandbox Execution
Recovery & HITL
```

所以接下来推荐顺序保持为：

```text
V3.6 Evidence Checker：系统知道证据够不够
V3.7 Context Builder：系统知道把什么上下文交给模型
V3.8 Conversation Memory：系统能处理多轮状态
V3.8.1 Conversation Compaction：系统能压缩旧历史并保留最近原文
V3.9 Agent Evaluation：系统能评估 agent 行为
V3.10 Production Core：系统具备 run、观测、配置和稳定性基础（已完成）
V3.10.1 Agent Console：用户能以会话界面查看答案、来源、Plan 和 Run 详情（已完成）
V3.10.2 Run Event Streaming：前端能实时接收节点和工具事件，不展示 chain-of-thought（已完成）
V3.10.3 LangGraph Advanced Patterns：系统能组合子图、并行步骤、动态路由、原生重试和消息流（已完成）
V3.11 Skill System：系统能选择并渐进式加载任务方法（已完成）
V3.11.1 Docling Structured Ingestion：系统能把多格式文档解析为统一结构并切片（已完成）
V3.11.2 Chunking Framework Comparison：系统能对比父子、层级自动合并和语义切片（已完成）
V3.11.3 Collection Router：系统能在有限知识库范围内路由并融合多库检索（已完成）
V3.12 MCP Integration：系统能接入标准化外部工具并对外提供 RAG 工具（已完成）
V3.12.1 AgentRuntime/Core Extraction：把完整执行内核、V3.12 MCP Adapter 和可见答案流迁移为稳定公共核心（已完成）
V3.12.2 Retrieval Reranking：系统能扩大 RRF 候选、使用 matched child 重排，并把 parent Top K 送入 Context（已完成）
V3.12.3 MCP Agent Integration：系统能复用 MCP 连接，让 Planner 自动选择只读 MCP Tool，并把 Tool Observation 送入 Context
V3.12.4 Unified Knowledge Routing：系统能在 Planner 确认 search 后选择知识库范围，并对跨库候选统一 Rerank
V3.13 Permission Policy：系统能在执行前判断 allow / confirm / deny（已完成静态策略版）
V3.14 Sandbox Execution：系统能在 Docker 隔离环境中执行受控文件和白名单命令（已完成）
V3.15 Recovery & HITL：系统能从中断和失败中恢复并等待人工输入（已完成）
```

除了这些纵向版本，还要逐步补上真实 harness 工程常见的横切能力：

```text
Run Lifecycle：run_id、status、latency、error、token/tool summary
Tool Registry：工具定义、工具白名单、工具执行和 ToolResult 统一抽象
Schema Contract：结构化输出 schema、解析失败 fallback、prompt/schema 版本
Checkpoint / Recovery：节点失败、重试、恢复、中间结果保存
```

这些能力不一定都单独成一个版本，但每次新增版本时都应该考虑是否需要引入一点点雏形。比如 V3.5 引入轻量 `ToolRegistry` 和 `StepResult`，V3.6 引入 retry，V3.10 再把 Run Lifecycle 和观测系统化，V3.15 最后补完整 checkpoint/recovery。

## 路线合理性复核

这条路线符合真实 Harness 的依赖关系，也保持了当前每个版本只学习一个主要概念的节奏：

1. `V3.8.1` 先控制 Context Window，否则长对话会让后续评测结果受上下文膨胀影响。
2. `V3.9` 先建立 Agent Evaluation，后续增加 Skill、MCP 和 Sandbox 时才能做行为回归。
3. `V3.10` 已补 Run Lifecycle 和观测，因为外部工具越多，越需要统一的 latency、token、error 和 tool summary。
4. `V3.10.1` 先用已有 JSON 构建 Agent Console，验证 `ProductionAskResponse` 的数据分层是否适合用户阅读，不引入实时传输变量。
5. `V3.10.2` 再把 V3.8.1 节点事件接入 EventSink / SSE；先推阶段事件和最终答案，不急于实现 token-by-token 输出。
6. `V3.11` 已学习 Skill Router，再接 MCP。两者技术上没有强制依赖，但 Skill 负责“采用什么工作方法”，MCP 负责“通过什么协议调用外部能力”，按这个顺序更容易区分职责。
7. `V3.12` 已先让普通低风险 MCP 工具通过稳定 Adapter 接入，验证协议适配和错误边界。
8. `V3.12.1` 再把 V3.8.1 Agent 内核和 V3.12 MCP Adapter 提升为无版本号 `AgentRuntime/Core`，并接入统一 Tool Registry，避免 Permission、Sandbox 继续依赖历史学习目录。
9. `V3.13` 必须在开放文件写入和 Shell 前完成。所有本地工具和 MCP 工具都统一经过 allow / confirm / deny 策略。
10. `V3.14` 只在 Sandbox 中执行高风险工具，不允许模型直接获得宿主机任意 Shell 权限。
11. `V3.15` 最后补跨节点恢复和 Human-in-the-loop，因为它依赖前面已经稳定的 Run、Tool、Policy 和 Sandbox 状态模型。

需要保持的三个概念边界：

```text
Skill：告诉 Agent 应该采用什么方法和流程
MCP：规定 Agent 如何发现和调用外部工具
Sandbox：规定工具真正在哪里、以什么资源和权限执行
```

每个阶段都建议保持之前的节奏：

```text
独立版本目录
Swagger JSON 接口
CLI 调试入口
测试
学习文档
SVG 流程图
断点调试说明
```

## Phase 0：复盘当前基础

目标：确认已经理解 V3.1-V3.3 的区别。

需要能回答：

- V3.1 Router 和 V3.2 Tool Calling 的区别是什么？
- 为什么 V3.2 仍然需要根据 `tool_call.name` 做工具分发？
- LangGraph 的 `State`、`Node`、`Edge` 分别是什么？
- `graph_path` 和 `trace` 有什么区别？
- `no_search`、`clarify`、`search_notes` 分别解决什么问题？

对应文件：

```text
obsidian_rag/v3_1/
obsidian_rag/v3_2/
obsidian_rag/v3_3/
docs/v3-1-llm-router-guide.md
docs/v3-2-tool-calling-guide.md
docs/v3-3-langgraph-guide.md
```

完成标准：

- 能用断点走完 `search_notes`、`no_search`、`clarify` 三条路径。
- 能解释 `AgentState` 如何在节点之间更新。
- 能说清楚为什么 LangGraph 不是让模型更聪明，而是让工作流更工程化。

## Phase 1：Planner

建议版本：`V3.4 Planner`

目标：学习 planner 如何把复杂问题拆成多个可执行步骤。

Planner 解决的问题：

```text
用户问题不是一步工具调用能完成时，先生成计划。
```

示例问题：

```text
帮我总结生鸡肉处理、厨房清洁、剩菜保存三类食品安全建议
```

Planner 输出可以是：

```json
{
  "steps": [
    {"id": "s1", "kind": "search", "query": "生鸡肉 清洗 交叉污染"},
    {"id": "s2", "kind": "search", "query": "厨房 清洁 洗手 抹布"},
    {"id": "s3", "kind": "search", "query": "剩菜 保存 冷藏 复热"},
    {"id": "s4", "kind": "synthesize", "instruction": "综合前三步形成答案"}
  ]
}
```

已实现：

- `obsidian_rag/v3_4/` 已新增。
- `PlannerService` 已新增。
- Planner 用 LLM 输出结构化 `Plan JSON`。
- Response 返回 `plan`、`trace`。
- 暂时不做复杂执行器，只验证 planner 能拆任务。

学习重点：

- planner vs router。
- plan schema 如何设计。
- 为什么 planner 不应该直接回答。
- 如何约束 planner 输出可执行步骤。

完成标准：

- 单步问题生成 1 个 search step。
- 多主题问题生成多个 search step。
- 实时外部问题生成 `no_search` 或不可执行计划。
- Swagger 可以看到完整 plan。

当前状态：

- `obsidian_rag/v3_4/` exists as a separate LangGraph planner package.
- `POST /planner/plan` is available from `obsidian_rag.v3_4.app`.
- `obsidian-rag agent-v3-4 plan "..."` runs the same planner workflow from CLI.
- The planner graph uses nodes: `build_prompt`, `call_planner`, and `parse_plan`.
- Response returns `plan`、`graph_path`、`trace`.
- V3.4 stops after plan generation and does not call `RetrievalService.search()` or Qdrant.
- V3.4 learning guide and diagrams live in `docs/v3-4-planner-guide.md`.

## Phase 2：Executor

建议版本：`V3.5 Planner Executor`

目标：学习 executor 如何按 plan 执行工具步骤。

Planner 只回答：

```text
应该做什么？
```

Executor 负责：

```text
逐步执行计划，并保存每步结果。
```

建议流程：

```text
planner
  -> execute_step_1
  -> execute_step_2
  -> execute_step_3
  -> synthesize_answer
```

建议实现：

- 扩展 LangGraph。
- `AgentState` 增加：
  - `run_id`
  - `plan`
  - `current_step_index`
  - `step_results`
  - `completed_steps`
- 新增轻量 `ToolRegistry`：
  - 注册 `search_notes`
  - 后续可注册 `no_search`、`clarify`、其它工具
  - 统一工具调用入口和 `ToolResult`
- 新增 `StepResult`：
  - `step_id`
  - `tool_name`
  - `query`
  - `result_count`
  - `sources`
  - `status`
- 每个 `search` step 通过 `ToolRegistry` 调用 `search_notes`。
- 最后 `synthesize_answer` 读取所有 step results。

学习重点：

- planner 和 executor 的职责边界。
- 多步工具调用如何串联。
- step result 如何进入最终回答。
- graph 如何表达循环或多步执行。
- 为什么真实 harness 通常需要 `ToolRegistry`，而不是在业务代码里到处 `if tool.name == ...`。
- `run_id`、`step_results`、`trace` 各自服务什么调试场景。

完成标准：

- 一个多主题问题能执行多个 search step。
- response 能展示每个 step 的 query、结果数、sources。
- 最终答案能综合多个 step result。
- trace 能看出每个 plan step 是如何被执行的。
- 执行失败时能返回结构化失败 step，而不是让整个接口 500。

当前状态：

- `obsidian_rag/v3_5/` exists as a separate LangGraph planner executor package.
- `POST /agent/ask` is available from `obsidian_rag.v3_5.app`.
- `obsidian-rag agent-v3-5 ask "..."` runs the same planner executor workflow from CLI.
- The graph uses nodes: `planner`, `execute_steps`, and `synthesize_answer`.
- Response returns `run_id`、`answer`、`plan`、`step_results`、`graph_path`、`trace`.
- V3.5 introduces a lightweight `ToolRegistry` and `StepResult`.
- V3.5 does not yet do evidence sufficiency check, retry search, or checkpoint recovery.
- V3.5 learning guide and diagrams live in `docs/v3-5-planner-executor-guide.md`.

## Phase 3：Evidence Checker

建议版本：`V3.6 Evidence Checker`

目标：学习 agent 如何判断证据是否足够，以及不够时如何重试或追问。

当前 V3.3 的 `evidence_check` 很轻：

```text
有 results -> 有证据
没 results -> 证据不足
```

真实 harness 里更像：

```text
检索结果是否覆盖了用户问题？
是否覆盖了每个 plan step？
答案有没有被来源支持？
是否需要换 query 再搜一次？
```

建议实现：

- 新增 `EvidenceCheckResult`：
  - `is_sufficient`
  - `missing_points`
  - `suggested_queries`
  - `reason`
- evidence checker 可以先用规则版，再升级 LLM 版。
- 如果证据不足，进入 `retry_search` 节点。
- 给 retry 增加停止条件：
  - 最多重试次数
  - 已尝试 query 列表
  - 没有新 query 时停止
- 为 evidence 节点保留 checkpoint 信息，方便看清楚失败发生在检索、证据覆盖还是答案生成。

学习重点：

- retrieval failure 和 answer failure 的区别。
- groundedness / faithfulness。
- coverage check。
- retry search 的停止条件。
- checkpoint / recovery：节点失败后，如何保留已经完成的 step results。

完成标准：

- 能识别“检索到了内容但没覆盖问题”的情况。
- 能返回缺失点。
- 能触发一次二次检索。
- trace 展示 evidence check 的判断依据。

当前状态：

- `obsidian_rag/v3_6/` exists as a separate LangGraph evidence-checking planner executor package.
- `POST /agent/ask` is available from `obsidian_rag.v3_6.app`.
- `obsidian-rag agent-v3-6 ask "..."` runs the same workflow from CLI.
- The graph uses nodes: `planner`, `execute_steps`, `evidence_check`, `retry_search`, and `synthesize_answer`.
- Response returns `run_id`、`answer`、`plan`、`step_results`、`retry_step_results`、`evidence_check`、`graph_path`、`trace`.
- V3.6 introduces `EvidenceCheckResult` and a bounded retry loop controlled by `max_retries`.
- V3.6 still does not include a formal Context Builder or multi-turn memory.
- V3.6 learning guide and diagrams live in `docs/v3-6-evidence-checker-guide.md`.

## Phase 4：Context Builder

建议版本：`V3.7 Context Builder`

目标：学习 harness 如何把用户问题、计划、检索证据、历史状态和约束组装成模型可用的上下文。

当前 V3.5/V3.6 里会有一个隐式上下文组装函数：

```text
_build_synthesis_messages(state)
```

它只是把 `question`、`plan`、`step_results` 拼进 prompt。真实 harness 里的 Context Builder 更像一个独立模块：

```text
AgentState -> select evidence -> format citations -> fit token budget -> build messages
```

建议实现：

- 新增 `ContextBuilder`：
  - 输入 `question`、`plan`、`step_results`、`evidence_check`。
  - 输出 `ContextBundle`。
- 新增 `ContextBundle`：
  - `messages`
  - `included_chunks`
  - `excluded_chunks`
  - `token_budget`
  - `context_summary`
- 把 V3.5/V3.6 里的 `_build_synthesis_messages()` 拆到 Context Builder。
- 对检索结果做简单排序和裁剪：
  - 优先保留带 `chunk_id` 的结果。
  - 优先保留 evidence check 认为相关的 step。
  - 超过预算时丢弃低分或重复 source。

学习重点：

- Context Builder 和 Retriever 的区别。
- Context Builder 和 Reporter/Synthesizer 的区别。
- 为什么不能把所有检索结果无脑塞给模型。
- token budget、source formatting、evidence ordering 的工程意义。

完成标准：

- response 能展示 `context_bundle` 摘要。
- trace 能看出哪些 chunks 被放进 prompt，哪些被裁掉。
- Swagger payload 不变，但 response 能解释最终答案使用了哪些上下文。
- 文档说明 Context Builder 是独立环节，不等于检索，也不等于最终回答。

当前状态：

- `obsidian_rag/v3_7/` exists as a separate LangGraph context-building planner executor package.
- `POST /agent/ask` is available from `obsidian_rag.v3_7.app`.
- `obsidian-rag agent-v3-7 ask "..."` runs the same workflow from CLI.
- The graph uses nodes: `planner`, `execute_steps`, `evidence_check`, `retry_search`, `build_context`, and `synthesize_answer`.
- Response returns `context_bundle.messages`、`included_chunks`、`excluded_chunks`、`token_budget`、`context_summary`.
- V3.7 only builds context from the current run and does not read/write persistent memory.
- V3.7 learning guide and diagrams live in `docs/v3-7-context-builder-guide.md`.

## Phase 5：Memory

建议版本：`V3.8 Conversation Memory`

目标：学习 harness 如何处理多轮对话状态。

当前工程每次请求都是单轮：

```text
request in -> answer out
```

Memory 阶段要引入：

```text
conversation_id
message history
previous tool calls
previous sources
bounded recent history
```

建议实现：

- 新增本地 SQLite memory store。
- request 增加 `conversation_id`。
- response 返回更新后的 conversation state。
- 支持追问：

```text
第一轮：生鸡肉要不要洗？
第二轮：那处理完厨房呢？
```

第二轮能理解“那”指的是上一轮的生鸡肉处理场景。

学习重点：

- short-term memory vs long-term memory。
- 对话历史裁剪。
- 什么时候历史应该参与检索 query。
- memory 和知识库检索的边界。

完成标准：

- 多轮追问能复用上一轮上下文。
- trace 能显示 memory 被读取。
- 不相关历史不会污染当前问题。

当前状态：

- `obsidian_rag/v3_8/` exists as a separate LangGraph conversation-memory package.
- `POST /agent/ask` and `GET /memory/{conversation_id}` are available from `obsidian_rag.v3_8.app`.
- `obsidian-rag agent-v3-8 ask "..." --conversation-id ...` runs the same workflow from CLI.
- The graph adds `load_memory` before planner and `save_memory` after synthesis.
- SQLite persists complete raw turns, sources, and tool calls.
- Planner and ContextBuilder receive only the most recent `memory_window` turns.
- V3.8 does not implement LLM summaries, rolling summaries, or vector memory retrieval.
- V3.8 learning guide and diagram live in `docs/v3-8-conversation-memory-guide.md`.

### V3.8.1 Conversation Compaction

目标：学习真实 Harness 如何避免把完整消息历史持续塞给 LLM。

核心结构：

```text
Raw Turns：SQLite 永久保留全部原始记录
Rolling Summary：压缩窗口之外的重要历史
Recent Turns：保留最近 memory_window 轮原文
```

实现状态：

- `obsidian_rag/v3_8_1/` 是独立版本目录。
- LangGraph 在 `load_memory` 和 `planner` 之间增加 `compact_memory`。
- 按未摘要旧 Turn 数量或估算 token 阈值触发压缩。
- 摘要使用 `existing_summary + new old turns` 滚动更新，不重扫全部历史。
- SQLite 保存 `summary_text`、`summary_through_turn_id`、`summary_updated_at`。
- 原始 `turns` 永不因压缩删除。
- Planner 和 Answer Context 使用 `summary_text + recent_turns`。
- `POST /memory/{conversation_id}/compact` 和 CLI `agent-v3-8-1 compact` 支持手动观察。
- 学习指南和流程图位于 `docs/v3-8-1-conversation-compaction-guide.md`。

V3.8.1 仍不做跨 conversation 用户画像、向量 Memory 检索、异步事实提取和事实置信度；这些不应和会话上下文压缩混为一层。

## Phase 6：Agent Evaluation

建议版本：`V3.9 Agent Evaluation`

目标：把 V2 的 evaluation 扩展到 agent 行为。

当前 V2 主要评估：

```text
retrieval metrics
answer coverage
```

Agent Evaluation 要评估：

```text
router 是否正确
tool call 是否正确
planner 是否合理
executor 是否按计划执行
evidence check 是否准确
最终 answer 是否 grounded
```

建议 eval set 字段：

```yaml
examples:
  - id: weather_no_search
    question: 今天深圳天气怎么样
    expected_tool: no_search
    expected_graph_path:
      - select_tool
      - no_search

  - id: chicken_search
    question: 生鸡肉要洗吗
    expected_tool: search_notes
    expected_source_files:
      - rag_test_food_safety_kb_expanded.md
    expected_answer_points:
      - 不建议清洗
      - 交叉污染
```

学习重点：

- 工具选择准确率。
- graph path 准确率。
- plan step coverage。
- executor step success rate。
- answer groundedness。
- regression test for agents。

完成标准：

- CLI 能跑 agent eval。
- Swagger 能提交单条 agent eval。
- 报告能区分 router/tool/planner/retrieval/answer 哪一层失败。

## Phase 7：Production Core

实现版本：`V3.10 Production Core`

目标：在继续增加工具类型之前，先建立统一的 Run Lifecycle、配置、观测和失败边界。

本次已实现的最小 Production Core：

- V3.10 `prod_...` run ID、`queued -> running -> succeeded/failed` 状态和生命周期事件。
- UTC 开始/结束时间与总 `duration_ms`。
- `graph_node_count`、`trace_event_count`、检索结果数与按工具名聚合的调用摘要。
- Answer prompt / 最终 answer 的启发式 token estimate，并明确不是供应商 usage。
- 标准化 `RunError`、安全的 `/runtime/config` 和进程内 `/runs` 查询。

本版刻意延后：请求 ID、LLM/Tool/Retrieval 分层耗时、真实 token usage、timeout/自动 retry/fallback、prompt/schema version、持久化或分布式 Run Store。这些能力需要先在 LLM Client、Tool Registry 和部署边界引入稳定的埋点，不能仅靠在响应外再包一层完成。

完成标准：

- 一次请求可以通过 `run_id` 串起 Planner、Tool、Memory 和 Answer 记录。
- response 或日志包含统一的 latency/token/tool/error summary。
- 能区分业务失败、工具失败、LLM 失败和超时。

## Phase 7.1：Agent Console

实现版本：`V3.10.1 Agent Console（JSON First）`

目标：把 V3.10 已经存在的 `ProductionAskResponse` 转换为可操作的 Vue 3 会话工作台，验证 Run、Plan、Tool、Evidence、Context 和 Memory 这些结构化数据是否对用户可理解。

本次实现：

- 当时的 `frontend/v3_10_1_agent_console/` 使用 Vite、Vue 3、TypeScript 和 `lucide-vue-next`；当前维护入口已迁移为 `frontend/agent_console/`。
- 桌面端提供会话侧栏、对话主区和 Run Inspector；移动端将 Inspector 收为侧边抽屉。
- 对话主区展示最终答案和来源；Inspector 分成概览、计划与工具、证据、上下文四个视图。
- 通过浏览器 `localStorage` 保存近期会话 ID 和轻量消息；通过 `GET /console/conversations/{conversation_id}` 读取 V3.10 SQLite Memory 快照。
- Vite dev proxy 将 `/api/*` 转发给 `127.0.0.1:8013`，因此开发环境不需要先引入 CORS。
- V3.10.1 FastAPI 保留 JSON `POST /agent/ask`、`GET /runs`、`GET /runs/{run_id}`，并增加 Console 配置和会话快照接口。

版本边界：

- 本版只在请求完成后一次性渲染 `ProductionAskResponse`；请求中的“运行中”是浏览器本地状态。
- 不把 `trace` 当作 chain-of-thought；界面只显示节点、工具、结果数和已有的原因说明。
- 不实现 SSE、token-by-token 输出、实时节点进度或多用户会话管理。
- 不改变 V3.8.1 Agent 和 V3.10 Runtime 的执行策略。

完成标准：

- 能在浏览器发起同一个 `conversation_id` 的追问，并查看 Memory 快照与本次 Run。
- 能清楚区分 `succeeded`、`failed`、`no_search`、`clarify` 和 Evidence 不足。
- 前端构建、前端单测、Python API/CLI 测试都可独立验证。

## Phase 7.2：Run Event Streaming

建议版本：`V3.10.2 Run Event Streaming`

目标：让 Agent 在运行过程中就把可观察事件交给前端，而不是等待完整 JSON 响应结束。

建议实现：

- 在 V3.8.1 节点和 Tool 执行边界引入 `EventSink` / `RunEventBus`。
- 先发送 `run_started`、`node_started`、`node_finished`、`tool_result`、`run_finished`、`run_failed` 等事实事件。
- 以 SSE 暴露事件；浏览器继续使用 V3.10.1 的 Inspector，但实时追加时间线。
- 第一版只发送阶段事件和最终答案，不做 LLM token delta；真实文本流式输出需要 LLM Client 新增 `stream()`。

版本边界：

- SSE 不是展示模型内部思考的接口。
- 不因为改用 SSE 删除 JSON `/agent/ask`；JSON 继续保留给 Swagger、CLI、测试和非流式调用方。

## Phase 7.3：LangGraph Advanced Patterns

学习版本：`V3.10.3 LangGraph Advanced Patterns`

目标：在已经理解 LangGraph 基础节点编排和 SSE 事件流之后，学习 LangGraph 如何支撑更复杂、更可恢复的 Harness 工作流。

### 主要学习内容

```text
Subgraph：把 RAG、审批、文件处理等流程封装成子图
Parallel / Send：并行执行多个主题检索，再汇总结果
Command：节点同时更新 State 并动态决定下一条路径
Retry Policy：区分业务 retry 和 LangGraph 节点级 retry
State History：查看每一步 State 变化，理解恢复和调试
messages Streaming：让 LLM 消息或答案增量进入现有 SSE
```

### 已实现的示例链路

```text
用户问题
  -> load / compact memory
  -> planner 子图
  -> Send 并行执行多个 search worker
  -> evidence 汇总节点
  -> Command 动态路由 retry / context
  -> answer messages 流
  -> save memory
```

### 与已完成版本的边界

| 版本 | 重点 |
| --- | --- |
| V3.10.2 | Agent 节点完成后，通过 EventBus 和 SSE 发送运行事实。 |
| V3.10.3 | 学习 LangGraph 内部的子图、并行、动态路由、状态历史和消息流。 |
| V3.11 | 在稳定的执行编排之上学习 Skill Registry 和 Skill Router。 |

V3.10.3 不引入 MCP、Permission、Sandbox 或新的业务知识库；重点是 LangGraph 执行模型本身。

### 已实现能力

- `PlannerSubgraphState` 和子图输入输出边界。
- `Send` 或等价 Map-Reduce 并行检索。
- `Command` 动态跳转和状态更新。
- 节点级 retry policy 与现有 Evidence retry 的对比。
- LangGraph Checkpointer 的最小实验和 State History 查看。
- 将 `messages` 流式输出接入现有 `answer_delta` SSE 设计，但不展示隐藏推理。

### 完成标准

- 能画出主图和子图的边界，并解释 State 如何进出子图。
- 能调试串行、并行、retry 和动态路由四条路径。
- 能查看某一步 State 的历史变化，并理解 Checkpointer 是后续恢复的基础；真正 resume 留到 V3.15。
- 能区分 `node_finished` 事件、`messages` 流和 token-by-token 最终答案。
- 能说明为什么 LangGraph 负责执行编排，而 Redis/NATS/Kafka 负责跨进程消息传输。

### 版本边界

- 本阶段不开放任意 Shell、文件写入和外部 MCP 工具。
- 不把模型隐藏推理或 chain-of-thought 推送到前端。
- 不把当前 V3.10.2 的 InMemory EventBus 直接宣称为生产级消息系统。

V3.10.3 已完成：`obsidian_rag/v3_10_3/` 提供 Planner Subgraph、`Send` 并行检索、`Command` 动态路由、`RetryPolicy`、`InMemorySaver` State History，以及 `updates/messages/custom` 多模式 SSE；JSON、CLI、Swagger、断点文档和 SVG 均保留。当前 Checkpointer 只在单进程内存中保存状态，不宣称已经实现跨重启恢复。

## Phase 8：Skill System

学习版本：`V3.11 Skill System`

目标：学习 Skill 与 Tool 的区别，以及如何按任务渐进式加载工作方法。

建议实现：

- `SkillManifest`：名称、描述、触发提示、入口文件和版本。
- `SkillRegistry`：发现和注册本地 Skills。
- `SkillRouter`：LLM 选择零个或一个 Skill，并返回结构化选择结果。
- 先只给模型 Skill 名称和简介，选中后才加载完整 `SKILL.md`。
- Planner 接收选中的 Skill Context，ToolRegistry 保持独立。

版本边界：

- Skill 负责“如何完成一类任务”，Tool 负责“执行一个具体动作”。
- 本版不接 MCP，不执行 Shell，不允许 Skill 绕过 ToolRegistry。

完成标准：

- 能调试 Skill 未命中、正确命中和错误命中三条路径。
- trace 展示候选 Skill、最终选择、加载文件和注入 token。

V3.11 已完成：本地 `SkillRegistry` 扫描 front matter，LLM Router 返回零个或一个结构化选择，选中后才加载 `SKILL.md`，并通过 `SkillAwarePlannerService` 注入现有 Planner；JSON、SSE、CLI、Swagger、断点文档和 SVG 均已提供。

V3.11 仍保持边界：不接 MCP、Permission、Sandbox、Shell，不让 Skill 绕过 `ToolRegistry` 执行动作。

### V3.11.1 Docling Structured Ingestion

V3.11.1 是 V3.12 MCP 前的数据基础插入版本，不改变 V3.11 Skill System：

```text
multi-format files -> Docling DocumentConverter -> DoclingDocument
                   -> HybridChunker atomic blocks + heading_path
                   -> adaptive parent-child (default)
                   -> child Embedding / Qdrant / KeywordIndex
                   -> parent expansion
```

学习重点：

- Docling 如何统一 PDF、Markdown、DOCX、PPTX、XLSX、HTML、CSV 和图片等输入。
- `DoclingDocument`、layout/OCR/table/provenance metadata 的职责。
- `HybridChunker` 如何结合文档结构与 tokenizer 上限。
- 为什么不能把每个 Docling block 一对一当成生产 chunk。
- 如何通用合并同父小块、递归拆分超长 parent，并保持 child 召回、parent 返回。
- 为什么框架输出仍需要映射到稳定的本地 `TextChunk` contract。

版本边界：

- 不自研 Document Tree、PDF Parser 或 OCR；超长文本切分复用 LangChain `RecursiveCharacterTextSplitter`。
- V3.11.2 的 LangChain Parent 实验结论已经迁移到共享摄取/检索；LlamaIndex Hierarchical 与 Semantic 仍只保留实验。
- 共享 V0 ingest 固定使用 Docling；旧 loader/字符切片不再作为运行时 backend，已有索引切换时需要 recreate。

### V3.11.2 Chunking Framework Comparison

V3.11.2 使用同一 Docling Markdown 和 embedding，对比三个 request-scoped 内存实验：

```text
LangChain RecursiveCharacterTextSplitter + ParentDocumentRetriever
LlamaIndex HierarchicalNodeParser + AutoMergingRetriever
LlamaIndex SemanticSplitterNodeParser + VectorStoreIndex
```

学习重点：

- 小 child 召回、大 parent 返回。
- LlamaIndex Node Relationship 与自动父级合并。
- embedding 语义距离驱动的切片边界。
- 为什么不同框架的 score 不能直接比较，必须回到真实问题集和证据完整性。

版本边界：

- compare 不修改共享 Qdrant，不调用 Answer LLM，不新增 SSE。
- 实验结果必须通过 V2 Hit Rate、MRR、Source Recall 和 Context 完整性复测后，才能决定是否接入共享检索。
- 完成后回到既定 V3.12 MCP Integration 主线。

### V3.11.3 Collection Router

V3.11.3 是 V3.12 MCP 前的查询路由专项插入版本：

```text
question -> explicit collection or LLM Collection Router
         -> limited collection scope
         -> per-collection hybrid retrieval
         -> cross-collection RRF
```

学习重点：

- 用 YAML Registry 管理知识库 ID、物理 collection 和路由描述。
- 显式 collection 优先，自动路由只从启用 candidates 中选择有限范围。
- 多 collection 分别复用现有 dense、keyword、hybrid 检索。
- 原始分数不可直接跨库比较，因此使用第二层 rank-only RRF。
- 单库失败不影响其他库结果，并通过 trace 暴露选择和融合过程。

版本边界：

- JSON-first，只提供 Registry、route、search 和 CLI，不接完整 Agent、Memory、Skill Runtime 或 SSE。
- 不实现 ACL、租户隔离、Qdrant sparse、reranker 或自动扫描全部 collection。
- 完成后回到既定 V3.12 MCP Integration 主线。

## Phase 9：MCP Integration

建议版本：`V3.12 MCP Integration`

目标：学习标准化外部工具协议，并把现有 `ToolRegistry` 扩展为本地工具和 MCP 工具统一入口。

建议分两步实现：

1. MCP Client：连接测试 MCP Server，执行 `tools/list` 和 `tools/call`，把结果转换成统一 `ToolResult`。
2. MCP Server：把本项目的 `search_notes`、`ask_notes` 等能力暴露给其它 MCP Client。

需要覆盖：

- MCP Server 连接生命周期和超时。
- MCP Tool schema 到本地 Tool schema 的适配。
- 工具重名、服务不可用、参数错误和返回值过大的处理。
- trace 中记录 server、tool、latency、status，不记录敏感参数。

版本边界：

- 第一批只接低风险、只读 MCP 工具。
- 不允许 MCP 工具绕过 ToolRegistry、Evaluation 和后续 Permission Policy。

V3.12 已完成：使用官方 Python MCP SDK 和 `stdio` Transport，实现短生命周期 `ClientSession`、`initialize`、`tools/list`、`tools/call`、Tool/Result Adapter、超时和结果大小边界、Demo MCP Server 与只读 RAG MCP Server；提供独立 FastAPI、Swagger JSON、CLI、`launch.json`、测试代码、断点文档和 SVG。当前先显式调用 MCP Tool，不让 LLM 自动选择，也不实现 Permission 或 Sandbox。V3.12.1 已把该 MCP Adapter 接入公共 Tool Registry。

## Phase 9.1：AgentRuntime/Core Extraction

建议版本：`V3.12.1 AgentRuntime/Core Extraction`

目标：把已经被 V3.9、V3.10 和 V3.11 复用的 V3.8.1 完整 Agentic RAG 内核，以及 V3.12 已验证的 MCP Adapter，提升为无版本号公共核心，使学习版本不再承担生产依赖中心的职责。

当前依赖形态：

```text
V3.11 Skill -> V3.10 Runtime -> V3.8.1 AgentService
V3.9 Evaluation -------------> V3.8.1 AgentService
V3.12 MCP Adapter（独立显式调用，尚未进入 Agent ToolRegistry）
```

目标依赖形态：

```text
AgentRuntime/Core
  <- V3.8.1 compatibility adapter
  <- V3.9 Evaluation adapter
  <- V3.10 Production Runtime
  <- V3.11 Skill Runtime
  <- V3.12 MCP compatibility adapter
  <- V3.13 Permission Runtime
```

建议迁移内容：

- 将稳定的 Agent Graph、State、Context Builder、Memory、Compaction、Evidence 和 Tool 执行契约迁入无版本号公共包，例如 `obsidian_rag/core/`。
- 将 `AgentService` 的依赖改为显式注入：Planner、ToolRegistry、MemoryStore、EventSink 和模型客户端。
- 保持统一的 `AgentRequest`、`AgentResponse`、`AgentEvent` 和 `ToolResult` 核心契约。
- 复用 V3.10.3 已验证的 messages stream，向 V3.10.2/V3.11 和 Agent Console 发布最终可见 `answer_delta`。
- 把 V3.12 的 `McpToolDefinition` 和调用结果通过 Adapter 接入公共 `ToolRegistry`，但仍不让 LLM 自动选择高风险工具。
- V3.8.1 和 V3.12 保留为学习版本，通过 re-export 或 compatibility adapter 调用公共核心，原有 CLI、Swagger 和断点材料仍可使用。
- V3.9-V3.11 逐步改为依赖公共核心；迁移期间保持 JSON/SSE 对外行为不变。
- 用现有 V3.9 Evaluation cases 做迁移前后行为对照，避免架构调整改变 Router、Planner、Retrieval、Memory 和 Answer 语义。

学习重点：

- 学习版本、公共核心和 Production Runtime 三者的依赖方向。
- 为什么公共核心不应该反向 import `v3_x` 目录。
- Port/Adapter 与依赖注入如何避免 Planner、Skill、MCP 直接耦合 Agent Graph。
- 本地 Tool 与 MCP Tool 如何共享统一描述、调用和结果契约。
- API response、内部 state 和前端 view model 为什么需要独立稳定契约。
- 如何进行保持行为不变的渐进式迁移，而不是一次性重写。

版本边界：

- 本阶段只做架构提升和 MCP Tool Adapter 接线，不新增 Agent 推理能力，不改变 Prompt、检索策略和 Memory 语义。
- 不在迁移中实现 Permission、Sandbox 或任意 Shell。
- 不立即删除 V3.8.1 和 V3.12；它们继续作为教学对照和兼容入口。
- 不要求所有历史版本一次性迁移，只迁移当前主线真实依赖到的模块。

完成标准：

- V3.10/V3.11 主线不再直接 import `obsidian_rag.v3_8_1`。
- 公共核心不 import 任意 `obsidian_rag.v3_x` 学习版本。
- V3.8.1 和 V3.12 原有 Swagger、CLI 和主要响应结构仍可使用。
- 本地 Tool 与 MCP Tool 能通过统一 Tool Registry 被发现和显式执行。
- JSON、SSE、Memory、Skill Planner 注入和前端 Console 的行为保持兼容。
- 文档能画清楚 Core、Adapter、Production Runtime 和学习版本之间的依赖方向。

V3.12.1 已完成：新增无版本号 `obsidian_rag/core/`，V3.10/V3.10.2/V3.11 主线不再直接依赖 V3.8.1 AgentService/schemas；本地 Tool 与 V3.12 MCP Tool 通过统一 Registry 被发现和显式执行；最终 Answer 支持 `answer_delta`、TTFT/生成耗时和非流式回退；Agent Console 使用单个 assistant 气泡增量展示并在终态补齐 sources、Run 和 Memory。Prompt、检索、Evidence 与 Memory 语义保持不变，不展示隐藏推理。

当前 Agent Console 已从学习版本号中解耦：`frontend/agent_console/` 只连接 V3.12.1 / 8020 提供的 `console.v1`，启动时通过 `/console/config` 做能力协商。后续 Swagger 版本不会自动复制一套前端；只有用户可见 Console 契约出现不兼容里程碑时，才把上一套真实实现冻结到 `frontend/snapshots/`。

`console.v1` 的会话历史现以 MySQL 为事实来源：`GET /console/conversations` 提供服务端列表，详情接口提供最近 20 条显示 Turn，`DELETE /console/conversations/{conversation_id}` 在事务内硬删除 Conversation 和关联 Turns。浏览器 `localStorage` 不再保存会话列表；未产生 Turn 的新会话只作为页面临时状态存在。

## V3.12.2 Retrieval Reranking 插入版本

V3.12.2 在进入 Permission Policy 前补齐生产 RAG 常见的检索质量环节，但不改变安全主线：Dense/Keyword 先扩大候选并执行 RRF，Parent-Child 结果去重后使用 `sentence-transformers CrossEncoder` 对 `query + matched_child_text` 重评分，最终把 `returned_parent_text` Top K 交给 ContextBuilder。系统保留 RRF 与 rerank 前后排名、模型和耗时，并在 dependency、timeout 或推理异常时 fail-open 回退 RRF。当前首个真实模型推荐 `BAAI/bge-reranker-v2-m3`，商业 Rerank API 和独立模型服务留待生产化阶段。完成后继续 V3.13 Permission Policy。

## V3.12.3 MCP Agent Integration

V3.12.3 基于 V3.12 的 MCP 协议实现、V3.12.1 的公共 Agent Core 与统一 Tool Registry，以及 V3.12.2 的检索质量链路，补齐“完整 Agent 自动使用 MCP Tool”的缺口。

建议实现：

- 配置驱动的 MCP Server Registry，不允许请求动态传入任意 Server URL。
- 同时支持本地 `stdio` 和服务间 `streamable_http` Transport。
- 通过 FastAPI lifespan 管理连接、持久 Session、重连和关闭，不再每个 `/ask` 启动一次子进程。
- Tool Definition Cache、TTL/通知刷新、Server namespace 和只读 allowlist。
- Tool Catalog Builder 将裁剪后的 Local/MCP Tool Schema 提供给 Planner。
- Planner 增加通用 tool step，Tool Executor 通过统一 `ToolRegistry` 调用；当前同步 Graph 节点由 MCP Worker 负责跨线程异步 I/O。
- MCP 结构化结果进入独立 `tool_observations`，不伪装成知识库 Chunk。
- Answer Context 同时包含 Memory、Knowledge Chunks 和 Tool Observations。
- trace/SSE 记录 connect、discover、select、call、retry 和 result，不展示隐藏推理或 Secret。

版本边界：

- 内置 Demo stdio Server 只作为学习、测试和离线开发 Fixture。
- 本项目内部检索继续直接调用本地 `search_notes`，不通过 MCP 绕回自身。
- 第一版只允许预配置、allowlist 中的只读 MCP Tool。
- 不开放写入 Tool、任意 Shell、Skill scripts、人工审批或 Sandbox。
- V3.13 已让所有 Local/MCP Tool Call 统一经过 Permission Policy；下一步进入 V3.14 Sandbox。

## V3.12.4 Unified Knowledge Routing

V3.12.4 将 V3.11.3 Collection Router、V3.12.2 Multi-Collection Reranking 与 V3.12.3 MCP Agent Integration 合并为完整 Agent 主链路。

已实现：

- `core/collections` 提供 `RetrievalScope`、`RetrievalScopeResolver`、Registry 和 LLM Router。
- Agent Core 仅在注入 Resolver 时增加 `resolve_retrieval_scope` 节点，旧版本 graph path 保持不变。
- 显式 Collection、自动路由、Router disabled 和 no-search 分支具有明确优先级。
- 多库检索使用 V3.12.2 `search_collections()`，不重复执行 V3.11.3 的旧第二层 RRF 链路。
- 每个最终 Chunk 保留 Collection、跨库候选和 Reranker 元数据。
- Agent Console 支持 Auto Collection、Router 参数、候选库和最终 RetrievalScope 展示。

版本边界：

- Collection Router 只决定本地知识库访问范围，不注册成 MCP Tool。
- 当前按一次 Agent Run 的原始问题选择全局 Scope，不为每个 search subquery 重复调用 Router。
- 不实现 Collection ACL、多租户授权或 Permission Policy；这些进入 V3.13。

## Phase 10：Permission Policy

建议版本：`V3.13 Permission Policy`

目标：在开放文件写入和 Shell 之前，建立统一的执行策略和人工审批流程。

建议实现：

- 工具风险等级：`safe`、`confirm`、`restricted`。
- Tool allowlist、参数 schema 校验、路径 scope 和知识库 scope。
- Policy Decision：`allow`、`confirm`、`deny`。
- LangGraph `interrupt/resume` 或等价状态，保存待审批 tool call。
- 审批记录和执行审计。
- 本地工具和 MCP 工具使用同一套 Policy Engine。

完成标准：

- 只读检索可自动执行。
- 高风险调用在执行前暂停并等待批准。
- 拒绝后返回结构化 ToolResult，不让整个 Agent 500。

当前状态：

- `obsidian_rag/core/permissions/` 已提供 Principal、Decision、Report、静态 Policy 和进程内 Audit Store。
- Core Agent 仅在注入 Policy 时增加 `authorize_steps`，旧版本 graph path 保持兼容。
- Local `search_notes`、MCP Tool、retry search 和显式 MCP call 统一经过 Policy。
- 支持 Tool allowlist、required permission、Collection scope、JSON Schema 与 `safe/confirm/restricted` 风险等级。
- `allow` 自动执行，`confirm` 结构化阻止并标记 skipped，`deny` 标记 failed；均不会让 Agent 500。
- Agent Console 支持 Principal 预设和 Permission Report 页签。
- 为保持渐进学习，V3.13 尚未实现真正的 LangGraph interrupt/resume；人工批准后恢复执行放到 V3.13.1 或 V3.15。

## Phase 11：Sandbox Execution

建议版本：`V3.14 Sandbox Execution`

目标：学习文件和 Shell 工具如何在隔离环境中执行，而不是直接获得宿主机权限。

建议实现：

- 每个 run 或 conversation 的独立 workspace。
- 文件读写只能访问允许的 Sandbox 路径。
- 命令超时、输出大小限制、进程终止和资源限制。
- 网络访问开关和环境变量白名单。
- 将生成文件登记为 Artifacts，并在 response/trace 中返回元数据。
- 所有 Sandbox Tool Call 先经过 V3.13 Policy Engine。
- V3.13 已将 V3.11 的 Skill Registry 和懒加载提升到 `obsidian_rag/core/skills/`；显式单/多 Skill 先确定，隐式候选经过 Trigger、BM25 和词项覆盖率匹配，仅在候选灰区或相互竞争时调用 LLM Skill Router。最终 Skill Context 在 Planner 前进入同一个 AgentState，仍不执行 scripts。

V3.14 已完成：新增 `obsidian_rag/core/sandbox/`，实现每 Run Workspace、路径逃逸和 Symlink 防护、短生命周期 Docker Container、`network=none`、只读根文件系统、Capability/CPU/内存/PID/超时/输出限制，以及 Artifact 的 hash、MIME、列表和下载。四个 `sandbox::*` Tool 进入统一 Registry、Planner Catalog、V3.13 Policy、Tool Observation、JSON/SSE 和共享 Agent Console。

V3.14 主线同时完成一次生产化收敛：Knowledge Base Catalog 直接进入 Planner，search step 在 `arguments.collections` 中选择知识库；`search_notes` 内部使用确定性 Core Policy 校验 Registry、数量上限和物理 Collection。独立 LLM Collection Router 只保留在 V3.11.3/V3.12.4 教学链路，生产主图不再固定增加一次 Router LLM。

V3.14 还将 V3.12.3 已稳定复用的 Tool Catalog、`kind="tool"` 执行、`ToolObservation`、Tool Evidence 和 Answer 汇总提升到 Core Agent。版本类继续保留学习语义和依赖装配，Sandbox 特有的 Tool 可见性、Run Context 与 Artifact 回传留在 V3.14 适配层。

版本边界：

- 不直接暴露任意宿主机 Shell。
- 第一版只支持少量白名单命令和临时目录。
- Secret 不进入普通 AgentState、trace 或工具输出。
- Docker 不可用时 fail closed，不降级成宿主机 `subprocess`。

## Phase 12：Recovery & HITL

建议版本：`V3.15 Recovery & HITL`

目标：学习长任务如何保存中间状态、从失败点恢复，并在需要时等待用户输入。

建议实现：

- 官方 LangGraph `PostgresSaver`、psycopg ConnectionPool 和明确的 checkpoint schema。
- Run、Approval、Tool 幂等结果使用 PostgreSQL 结构化字段与 `JSONB`；Conversation Memory 继续使用 MySQL。
- run/step 幂等键，避免恢复后重复执行有副作用的工具。
- 节点失败重试、从指定 checkpoint 恢复。
- clarify、permission approval 和外部等待统一为 Human-in-the-loop 状态。
- resume 后继续原 graph，而不是重新执行完整请求。

完成标准：

- Agent 可以在等待审批时安全退出请求。
- 重启服务后可以加载 checkpoint 继续执行。
- 已成功执行的有副作用工具不会因恢复而重复运行。

## 推荐执行节奏

后续保持“一个版本解决一个主要问题”的节奏：

```text
V3.8.1：已完成 Context Compaction 学习和复盘
V3.9  ：已建立 Agent Evaluation 基线
V3.10 ：已补最小 Run Lifecycle、观测和错误边界
V3.10.1：已用 Vue Agent Console 消费 JSON Run / Agent Response
V3.10.2：用 SSE 推送真实运行事件（已完成）
V3.10.3：实现 Subgraph、Send、Command、RetryPolicy、State History 和 messages stream（已完成）
V3.11 ：实现 Skill Registry、Skill Router 和渐进式加载（已完成）
V3.12 ：先作为 MCP Client 调工具，再把 RAG 暴露为 MCP Server（已完成）
V3.12.1：完成公共 Agent Core、统一 Tool Registry 和最终可见答案流（已完成）
V3.12.2：完成 CrossEncoder Retrieval Reranking 和 fail-open（已完成）
V3.12.3：让完整 Agent 通过生产形态自动选择并执行只读 MCP Tool（已完成）
V3.12.4：融合 Collection Router、多库 Reranking 与 MCP Agent（已完成）
V3.13 ：建立工具风险分级和人工审批
V3.14 ：在 Permission Policy 后开放 Sandbox 文件和 Shell 工具
V3.15 ：补 Checkpoint、恢复和 Human-in-the-loop
```

不要把 V3.10～V3.15 合并成一个“大而全”的 Production Harness。它们分别解决观测、方法选择、协议适配、安全策略、隔离执行和恢复问题，合并实现会掩盖这些模块之间的职责边界。

## V3.10.2 完成复盘

V3.10.2 已在复用的 Agent Console 上接入 Run Event Streaming。进入 V3.11 前应能解释：

- V3.9 的离线行为评分和 V3.10 的单次在线 Run 观察有什么区别。
- 为什么 `prod_...` 和 V3.8.1 的 `run_...` 不能混为一个 ID。
- 为什么 `InMemoryRunStore` 与 SQLite Conversation Memory 不是同一类存储。
- 为什么 `token_estimate` 不能当作供应商真实 usage 或成本。
- 为什么 V3.10.1 的 JSON UI 只能知道“请求中 / 已完成”，而 V3.10.2 可以真实显示节点实时进度。
- 为什么 `trace` 是可观察执行事实，而不是 chain-of-thought。
- 为什么 SSE 应保留 JSON 接口作为 Swagger、CLI 和测试的稳定契约。

## V3.10.3 完成复盘

V3.10.3 完成后，应能解释：

- `graph.stream(values)` 和 `messages` 流分别传递什么。
- 为什么节点计时事件和 LLM token 增量事件属于两种不同的观察粒度。
- 为什么复杂流程需要 Subgraph 和并行，而不是继续把所有逻辑堆进一个 AgentState。
- 为什么业务补搜 retry 和 LangGraph 节点 retry policy 需要分开设计。
- 为什么 `Send` 并行写入 `step_results` 时需要 reducer。
- 为什么 `thread_id` 的 State History 和 `conversation_id` 的 MySQL Memory 不是同一类状态。
- 为什么 `InMemorySaver` 能演示 checkpoint，但还不能承担跨重启 resume。

V3.9 会继续作为行为回归基线，V3.10～V3.10.2 会为后续 Skill、MCP、Permission 和 Sandbox 提供运行观察与用户界面基线。

V3.11 开始前，还应能解释：

- Skill 为什么是方法上下文，而不是 Tool Calling 的另一种名称。
- 为什么 Registry 只读取 front matter，正文必须在选中后才加载。
- 为什么 `skill_name` 强制调试分支不能替代正常 LLM Router。
- 为什么 Router JSON 解析失败可以安全降级为 no-skill，而不能阻断旧 RAG Agent。
- 为什么 Skill Context 先注入 Planner，后续 Tool、Evidence、Context、Answer 和 Memory 仍保持独立。
