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
```

当前工程已经包含 intent router 能力：

- V3.1 是显式 router：模型输出 `RouterDecision JSON`。
- V3.2/V3.3 是隐式 router：模型通过 `tool_calls` 选择 `search_notes`、`no_search`、`clarify`。

所以 V3.7 之后可以继续学习 harness 的其它核心章节，尤其是 Conversation Memory。

## 总体学习路线

```text
Phase 0：复盘当前 Agentic RAG 基础
Phase 1：Planner，复杂任务拆解
Phase 2：Executor，按计划执行工具步骤
Phase 3：Evidence Checker，证据覆盖与重试
Phase 4：Context Builder，组装可控上下文
Phase 5：Memory，对话状态和长期记忆
Phase 6：Agent Evaluation，评估 router/tool/planner/answer
Phase 7：Production Harness，配置、权限、观测、成本和稳定性
```

## Harness 模块映射

附件里的总结可以作为后续学习路线的总框架：

```text
AI Agent = LLM + Harness
```

其中 LLM 负责思考、生成、推理、规划；Harness 负责让模型行为变成可控的软件流程。后续版本会逐步覆盖图里的核心模块，但不会一次性塞进一个版本。

| Harness 模块 | 本项目对应版本 | 当前状态 |
| --- | --- | --- |
| Context / 上下文 | V3.7 Context Builder | 目前只有 `_build_synthesis_messages()` 这种隐式拼接，还没有独立模块。 |
| Tool Calling / 工具调用 | V3.2、V3.3、V3.5 | 已覆盖：模型选择工具、LangGraph 编排、`ToolRegistry` 执行工具。 |
| File I/O / 文件读写 | V0、V1 | 已覆盖基础：Markdown/PDF loader、chunk、ingest。后续不作为 agent 主线重点。 |
| Shell Execution / 终端执行 | 暂不进入 RAG 主线 | 当前项目是知识库 RAG，不计划让 agent 直接执行 shell，避免学习目标发散。 |
| Permissions / 权限审批 | V3.10 Production Harness | 后期补：工具白名单、危险工具审批、知识库 scope 控制。 |
| Memory & State / 记忆状态 | V3.3、V3.5、V3.8 | 已有 `AgentState` 短期状态；V3.8 再做多轮 conversation memory。 |
| Orchestrator / 任务编排 | V3.3、V3.4、V3.5、V3.6 | 已用 LangGraph 表达 node/edge；V3.6 会加入 evidence/retry 分支。 |
| Verification / 测试验证 | V2、V3.6、V3.9 | V2 是 retrieval/answer eval；V3.6 是运行时 evidence check；V3.9 做 agent eval。 |
| Observation / 返回观察 | V3.5、V3.6、V3.10 | 已有 `trace`、`step_results`；后续补 latency、tool summary、error summary。 |
| Reporter / 汇总输出 | V3.5、V3.7 | 已有 `synthesize_answer`；V3.7 会把上下文构建从 reporter 中拆出去。 |

这张图里的模块都会涉及，但节奏上分两类：

- 主线必学：`Context`、`Tool Calling`、`Memory & State`、`Orchestrator`、`Verification`、`Observation`、`Reporter`。
- 后期或可选：`Permissions`、`Shell Execution`、更完整的 `File I/O`。这些更偏生产安全和通用 agent 平台，不适合太早压进当前 RAG 学习线。

当前到 V3.7 为止，项目已经覆盖了：

```text
Planner -> Orchestrator -> Tool Executor -> State -> Evidence Checker -> Context Builder -> Reporter
```

还缺的关键层是：

```text
Conversation Memory
Agent Evaluation
Production Harness
```

所以接下来推荐顺序保持为：

```text
V3.6 Evidence Checker：系统知道证据够不够
V3.7 Context Builder：系统知道把什么上下文交给模型
V3.8 Conversation Memory：系统能处理多轮状态
V3.9 Agent Evaluation：系统能评估 agent 行为
V3.10 Production Harness：系统具备权限、观测、稳定性雏形
```

除了这些纵向版本，还要逐步补上真实 harness 工程常见的横切能力：

```text
Run Lifecycle：run_id、status、latency、error、token/tool summary
Tool Registry：工具定义、工具白名单、工具执行和 ToolResult 统一抽象
Schema Contract：结构化输出 schema、解析失败 fallback、prompt/schema 版本
Checkpoint / Recovery：节点失败、重试、恢复、中间结果保存
```

这些能力不一定都单独成一个版本，但每次新增版本时都应该考虑是否需要引入一点点雏形。比如 V3.5 适合引入轻量 `ToolRegistry` 和 `StepResult`，V3.6 适合引入 retry/checkpoint，V3.10 再系统化成生产 harness。

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
user preferences
```

建议实现：

- 新增简单本地 memory store。
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

## Phase 7：Production Harness

建议版本：`V3.10 Production Harness`

目标：学习真实工程上线时需要的外围能力。

可能包含：

- Run Lifecycle：
  - run_id
  - request_id
  - status
  - started_at / ended_at
  - latency_ms
- 配置管理：
  - 不同模型
  - 不同工具开关
  - 不同知识库 scope
- 权限：
  - 哪些用户能访问哪些 vault
  - 工具调用白名单
- 观测：
  - latency
  - token usage
  - tool call count
  - error rate
- 稳定性：
  - timeout
  - retry
  - fallback
  - rate limit
- Schema Contract：
  - prompt version
  - output schema version
  - parse failure fallback
  - invalid output repair
- 成本：
  - 每次请求 token 统计
  - 模型调用次数
  - 工具调用次数

学习重点：

- agent 不是只要能回答，还要可控、可观测、可恢复。
- trace 面向调试，metrics 面向系统健康。
- 生产 harness 需要把模型行为变成可管理的软件系统。

完成标准：

- 每次 agent run 有结构化 run id。
- response 或日志包含 token/tool/latency summary。
- 常见错误有清晰 fallback。
- 文档说明如何排查一次 agent run。

## 推荐执行节奏

不要一次实现所有阶段。建议节奏：

```text
第 1 轮：复盘 V3.4 Planner，确认只生成 plan、不执行 RAG
第 2 轮：复盘 V3.5 Executor，确认 plan steps 如何变成 step_results
第 3 轮：暂停复盘，把 Planner/Executor 职责边界彻底吃透
第 4 轮：设计 V3.6 Evidence Checker，明确 coverage / retry / checkpoint
第 5 轮：实现 V3.6 Evidence Checker 和 retry/checkpoint
第 6 轮：设计 V3.7 Context Builder，明确上下文选择、裁剪和格式化
第 7 轮：实现 V3.7 Context Builder，把 prompt 拼接从 reporter 中拆出去
```

优先级最高的是：

```text
V3.6 Evidence Checker
```

因为它会把你从：

```text
系统按计划执行多个工具步骤
```

推进到：

```text
系统判断证据是否足够，不够时能重试或追问
```

这是 harness 工程从“系统会做”走向“系统知道自己做得够不够”的关键一层。

## 下一步建议

下一步不要直接写代码，先制定 `V3.6 Evidence Checker` 设计：

- Evidence check 应该检查整个 answer，还是逐个 plan step 检查？
- `EvidenceCheckResult` schema 应该包含哪些字段？
- coverage 不足时，是 retry search，还是 clarify？
- retry query 由规则生成，还是 LLM 生成？
- 最多 retry 几次？
- checkpoint 应该保存哪些中间状态？
- 如何在 response/trace 中展示证据不足的原因？

建议 V3.6 的第一版先做：

```text
用户问题 -> planner -> execute search steps -> evidence_check -> synthesize answer
```

等 evidence checker 理解清楚后，下一步不是直接进入 memory，而是先进入 `V3.7 Context Builder`。原因是 memory 读出来的信息最终也要经过 Context Builder 进入模型上下文；如果没有这层，后续 memory 很容易变成“把历史消息全塞进 prompt”的粗糙实现。
