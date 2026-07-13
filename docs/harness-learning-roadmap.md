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
```

当前工程已经包含 intent router 能力：

- V3.1 是显式 router：模型输出 `RouterDecision JSON`。
- V3.2/V3.3 是隐式 router：模型通过 `tool_calls` 选择 `search_notes`、`no_search`、`clarify`。

V3.9 已建立 Agent 行为回归基线；V3.10 已把运行生命周期、观测和错误摘要系统化。下一步可以进入 Skill System。

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
Phase 8：Skill System，Skill Registry、Skill Router 和渐进式加载
Phase 9：MCP Integration，连接外部 MCP 并暴露本地 RAG 能力
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
| Skills / 技能系统 | V3.11 | 下一步补：Skill Registry、LLM Skill Router、按需加载 `SKILL.md`。 |
| MCP / 外部工具协议 | V3.12 | 后续补：MCP Client、MCP Tool Adapter，以及把本地 RAG 暴露为 MCP Server。 |
| File I/O / 文件读写 | V0、V1 | 已覆盖基础：Markdown/PDF loader、chunk、ingest。后续不作为 agent 主线重点。 |
| Shell Execution / 终端执行 | V3.14 Sandbox Execution | 后期只在隔离 Sandbox 中开放，不直接把宿主机 Shell 暴露给模型。 |
| Permissions / 权限审批 | V3.13 Permission Policy | 在 Sandbox 前补工具白名单、风险等级、参数校验、scope 和人工审批。 |
| Memory & State / 记忆状态 | V3.3、V3.5、V3.8、V3.8.1 | 已有 AgentState、SQLite Raw Turns、最近窗口和滚动摘要。 |
| Orchestrator / 任务编排 | V3.3、V3.4、V3.5、V3.6 | 已用 LangGraph 表达 node/edge；V3.6 会加入 evidence/retry 分支。 |
| Verification / 测试验证 | V2、V3.6、V3.9 | V2 是 retrieval/answer eval；V3.6 是运行时 evidence check；V3.9 Lite 用 case contract 评测 routing、plan、tool、retrieval、evidence 和 answer。 |
| Observation / 返回观察 | V3.5、V3.6、V3.10 | 已有 `trace`、`step_results`；V3.10 已补 `RunRecord`、latency、tool summary、token estimate 和 error summary。 |
| Reporter / 汇总输出 | V3.5、V3.7 | 已有 `synthesize_answer`；V3.7 会把上下文构建从 reporter 中拆出去。 |
| Checkpoint / 恢复 | V3.15 | 后续补节点恢复、interrupt/resume、幂等和 Human-in-the-loop。 |

这张图里的模块都会涉及，但节奏上分两类：

- 主线必学：`Context`、`Tool Calling`、`Memory & State`、`Orchestrator`、`Verification`、`Observation`、`Reporter`。
- 后期或可选：`Permissions`、`Shell Execution`、更完整的 `File I/O`。这些更偏生产安全和通用 agent 平台，不适合太早压进当前 RAG 学习线。

当前到 V3.9 为止，项目已经覆盖了：

```text
Memory Reader -> Planner -> Orchestrator -> Tool Executor -> Evidence Checker -> Context Builder -> Reporter -> Memory Writer
                                                              -> Agent Evaluation
```

还缺的关键层是：

```text
Production Core
Skill System
MCP Integration
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
V3.11 Skill System：系统能选择并渐进式加载任务方法
V3.12 MCP Integration：系统能接入标准化外部工具并对外提供 RAG 工具
V3.13 Permission Policy：系统能在执行前判断 allow / confirm / deny
V3.14 Sandbox Execution：系统能在隔离环境中执行文件和 Shell 工具
V3.15 Recovery & HITL：系统能从中断和失败中恢复并等待人工输入
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
4. `V3.11` 将学习 Skill Router，再接 MCP。两者技术上没有强制依赖，但 Skill 负责“采用什么工作方法”，MCP 负责“通过什么协议调用外部能力”，按这个顺序更容易区分职责。
5. `V3.12` 先让普通低风险 MCP 工具接入统一 `ToolRegistry`，验证协议适配和错误边界。
6. `V3.13` 必须在开放文件写入和 Shell 前完成。所有本地工具和 MCP 工具都统一经过 allow / confirm / deny 策略。
7. `V3.14` 只在 Sandbox 中执行高风险工具，不允许模型直接获得宿主机任意 Shell 权限。
8. `V3.15` 最后补跨节点恢复和 Human-in-the-loop，因为它依赖前面已经稳定的 Run、Tool、Policy 和 Sandbox 状态模型。

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

建议实现：

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

## Phase 8：Skill System

建议版本：`V3.11 Skill System`

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

版本边界：

- 不直接暴露任意宿主机 Shell。
- 第一版只支持少量白名单命令和临时目录。
- Secret 不进入普通 AgentState、trace 或工具输出。

## Phase 12：Recovery & HITL

建议版本：`V3.15 Recovery & HITL`

目标：学习长任务如何保存中间状态、从失败点恢复，并在需要时等待用户输入。

建议实现：

- LangGraph checkpointer 和明确的 checkpoint schema。
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
V3.11 ：实现 Skill Registry、Skill Router 和渐进式加载
V3.12 ：先作为 MCP Client 调工具，再把 RAG 暴露为 MCP Server
V3.13 ：建立工具风险分级和人工审批
V3.14 ：在 Permission Policy 后开放 Sandbox 文件和 Shell 工具
V3.15 ：补 Checkpoint、恢复和 Human-in-the-loop
```

不要把 V3.10～V3.15 合并成一个“大而全”的 Production Harness。它们分别解决观测、方法选择、协议适配、安全策略、隔离执行和恢复问题，合并实现会掩盖这些模块之间的职责边界。

## 下一步建议

V3.10 已完成最小 Production Core，下一步进入 V3.11 Skill System。进入前应能解释：

- V3.9 的离线行为评分和 V3.10 的单次在线 Run 观察有什么区别。
- 为什么 `prod_...` 和 V3.8.1 的 `run_...` 不能混为一个 ID。
- 为什么 `InMemoryRunStore` 与 SQLite Conversation Memory 不是同一类存储。
- 为什么 `token_estimate` 不能当作供应商真实 usage 或成本。
- 为什么需要先有统一 Run 观察，再让 Skill Router、MCP 和高风险工具扩展运行链路。

V3.9 会继续作为行为回归基线，V3.10 会为后续 Skill、MCP、Permission 和 Sandbox 提供运行观察基线。
