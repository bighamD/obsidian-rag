# V3.15 Recovery & HITL 学习指南

V3.15 在 V3.14 Sandbox Execution 后增加持久 Checkpoint、`interrupt/resume`、人工审批和副作用 Tool 幂等保护。它解决的不是“模型如何回答”，而是“Agent 暂停或进程重启后如何可靠继续”。

## 相比 V3.14 新增什么

```text
V3.14：confirm → blocked StepResult → 本轮继续汇总
V3.15：confirm → interrupt → PostgreSQL Checkpoint → 人工决定 → Command(resume) → Tool Executor
```

新增能力：

- 官方 `LangGraph PostgresSaver` 持久保存 Graph 中间状态。
- `approval_gate` 在 Tool 执行前调用 `interrupt()`。
- V3.15 将 `sandbox::write_file`、`sandbox::run_command` 从 V3.14 教学默认的 `safe` 提升为 `confirm`。
- Run 增加 `waiting_for_approval` 状态。
- 支持 `allow`、`deny`、`edit` 三种人工决定。
- 服务重启后仍可用同一个 `run_id/thread_id` 恢复。
- 节点异常后可从最近 Checkpoint 重试失败节点。
- 成功副作用 Tool 使用持久幂等结果，节点重放时不重复执行。
- Agent Console 显示审批步骤、参数和恢复操作。

## 版本边界

本版本做：

- PostgreSQL Checkpoint、Run、审批和 Tool 幂等 Store，使用连接池支持多线程与多实例扩展。
- 单审批人、整批 confirm steps 的一次决定。
- JSON 与 SSE 都能返回暂停状态；恢复同时提供 JSON/SSE 接口。
- `edit` 后重新执行 Policy Schema 校验，再把仍为 `confirm` 的步骤视为人工允许。

本版本不做：

- 不做 Redis/Kafka/Celery 等分布式任务调度。
- 不做多人会签、审批超时、审批转交或复杂 RBAC。
- 不保证跨 Run 的业务幂等；那需要业务唯一键或外部系统幂等 API。
- 不把 Checkpoint 当 Conversation Memory 使用。

## 端到端主流程

![V3.15 HITL 暂停与恢复简化时序](assets/rag-v3-15-hitl-sequence-simple.svg)

这张图只保留三段核心时序。需要查看 Planner、持久层、Tool Executor 和 Memory 的完整关系时，再参考文末的“详细 HITL 架构图”。

```text
Planner
→ authorize_steps
→ approval_gate
   ├─ 无 confirm：直接继续
   └─ 有 confirm：interrupt(payload)
        → PostgresSaver 保存 AgentState / next node / interrupt
        → Run = waiting_for_approval
        → 人工 allow / deny / edit
        → Command(resume=decision)
→ execute_steps
→ evidence_check
→ build_context
→ synthesize_answer
→ save_memory
```

`interrupt()` 并不是抛出普通业务异常。LangGraph 捕获暂停信号，把当前 thread 的 checkpoint 保存下来，并在返回值与 `StateSnapshot.interrupts` 中暴露 payload。

暂停时 `approval_gate` 尚未正常返回，因此响应里的 `graph_path` 通常结束于 `authorize_steps`；真正判断暂停位置应查看 `StateSnapshot.next == ("approval_gate",)` 和 `StateSnapshot.interrupts`。恢复后该节点正常返回，`approval_gate` 才会进入 `graph_path` 与 timing。

## LangGraph 执行流程恢复的准确含义

V3.15 所说的“恢复”主要是恢复 LangGraph 的执行现场，不是单纯恢复前端连接。需要区分 HITL Resume、失败 Retry 和前端重连。

### 暂停发生在哪个节点

`authorize_steps` 只负责生成 `allow/confirm/deny` 权限判断，它会正常执行完成。真正调用 `interrupt()` 并暂停 Graph 的是下一个 `approval_gate`：

```text
authorize_steps
    → 正常完成并保存 Checkpoint
approval_gate
    → 保存 pending ApprovalRequest
    → interrupt(payload)
    → PostgresSaver 保存 AgentState、next nodes 和 interrupt
    → Run = waiting_for_approval
```

此时 HTTP 连接不是报错或异常断开：

- JSON 接口正常返回 `waiting_for_approval`。
- SSE 接口发送等待审批相关事件后结束当前 Stream。
- Python 线程不会留在内存里阻塞等待用户点击。
- FastAPI 服务即使随后重启，PostgreSQL 中的执行现场仍然存在。

### 审批后从哪里继续

用户提交 `allow`、`edit` 或 `deny` 时调用 Resume 接口，而不是失败恢复接口：

```text
POST /approvals/{run_id}/resume
    → 使用 run_id 作为 LangGraph thread_id
    → 从 checkpoint_* 读取最新 StateSnapshot
    → Command(resume=decision)
    → 重新进入 approval_gate
    → interrupt() 返回本次 decision
    → approval_gate 正常完成
    → execute_steps
```

LangGraph 不会从 Python 函数的 `interrupt()` 下一行进行物理续跑。Resume 时会从头重新执行 `approval_gate` 节点；当代码再次运行到同一个 `interrupt()` 调用时，它会返回本次 Resume 传入的决定，不再重复暂停。

因此 `interrupt()` 之前的副作用必须可重放。当前 `save_pending_approval()` 以 `run_id` 为唯一键幂等保存，同一个 `approval_gate` 重放不会重复创建审批记录。

三种决定都会恢复 Graph，但后续行为不同：

| 决定    | 恢复后的行为                                                                    |
| ------- | ------------------------------------------------------------------------------- |
| `allow` | 保留 Planner 原始 arguments，将 confirm 转为 allow，然后执行 Tool               |
| `edit`  | 替换指定 Step arguments，重新执行 Policy 校验，再执行通过校验的 Tool            |
| `deny`  | 将 confirm 转为 deny，不调用 Tool，生成拒绝 StepResult 后继续 Context 与 Answer |

### Resume、Retry 与前端重连

| 场景               | 使用的数据                        | 入口                         | 实际含义                                                  |
| ------------------ | --------------------------------- | ---------------------------- | --------------------------------------------------------- |
| 等待人工审批       | `hitl_approvals` + `checkpoint_*` | `/approvals/{run_id}/resume` | 使用 `Command(resume=decision)` 继续被 interrupt 的 Graph |
| 节点执行异常       | `hitl_runs` + `checkpoint_*`      | `/recoveries/{run_id}/retry` | 从最近可恢复 Checkpoint 重新执行失败流程                  |
| 前端刷新或重新连接 | `hitl_runs` + `hitl_approvals`    | Console 查询接口             | 只恢复页面展示，不会自动推动 Graph 执行                   |

等待审批的 Run 不能调用失败 Retry。`recover()` 检测到 `snapshot.interrupts` 时会拒绝恢复，并要求改用审批 Resume。反过来，只有节点异常且 `snapshot.next` 仍然存在时，才属于 `/recoveries/{run_id}/retry` 的处理范围。

可以记成：

```text
前端重连  = 恢复界面
审批 Resume = 恢复被 interrupt 的 Graph
失败 Retry   = 从 Checkpoint 重试失败流程
```

## 三类状态

![Memory、RunStore 与 Checkpoint](assets/rag-v3-15-state-layers.svg)

| 状态                 | 主键                           | 保存内容                          | 主要消费者              |
| -------------------- | ------------------------------ | --------------------------------- | ----------------------- |
| Conversation Memory  | `conversation_id`              | 原始 Turns、滚动摘要              | Planner、Answer Context |
| Run Store            | `run_id`                       | 生命周期、耗时、错误、metrics     | API、Agent Console      |
| LangGraph Checkpoint | `thread_id`，本版等于 `run_id` | AgentState、next nodes、interrupt | LangGraph resume        |

第五次对话是否携带前三轮，是 Memory 的问题；某个 Graph 是否停在 `approval_gate`，是 Checkpoint 的问题；前端显示“等待审批”，是 Run Store 的问题。

## 审批决定

### allow

把当前 `confirm` PermissionDecision 转成 `allow`，保持原 Plan arguments，继续执行。

### deny

把当前 `confirm` 转成 `deny`。`execute_steps` 会生成 blocked/failed StepResult，不调用 Tool，但 Graph 仍会进入 Context 和 Answer，让用户得到可解释结果。

### edit

按 `step_id` 替换 Tool arguments，然后重新调用 Permission Policy：

```text
edited Plan
→ JSON Schema / allowlist / permission / scope 再校验
→ deny 保持 deny
→ confirm 由本次人工审批转换为 allow
→ Tool Executor
```

## 幂等保护

![恢复与幂等保护](assets/rag-v3-15-resume-idempotency.svg)

幂等键：

```text
SHA-256(run_id + step_id + tool_name + canonical arguments JSON)
```

Tool 成功后把完整 `StepResult` 写入 `hitl_tool_results`。同一节点因恢复而重放时，如果 key 已存在，就返回缓存结果并设置：

```json
{
	"idempotency_hit": true
}
```

当前只缓存 `success`。失败结果不缓存，允许修复环境后再次恢复。

## PostgreSQL 数据库与表

V3.15 默认连接：

```text
postgresql://当前系统用户@127.0.0.1:5432/obsidian_rag_v315
```

环境变量：

```env
RAG_V3_15_POSTGRES_DSN=postgresql://user:password@127.0.0.1:5432/obsidian_rag_v315
RAG_V3_15_POSTGRES_SCHEMA=public
RAG_V3_15_POSTGRES_POOL_MIN_SIZE=1
RAG_V3_15_POSTGRES_POOL_MAX_SIZE=8
```

官方 `PostgresSaver` 管理：

| 表                      | 作用                              |
| ----------------------- | --------------------------------- |
| `checkpoint_migrations` | LangGraph Checkpoint 表结构版本   |
| `checkpoints`           | Checkpoint 元数据、父子关系和版本 |
| `checkpoint_blobs`      | AgentState channel 的序列化值     |
| `checkpoint_writes`     | 节点执行过程中的 pending writes   |

V3.15 Runtime Store 管理：

| 表                       | 作用                                                   |
| ------------------------ | ------------------------------------------------------ |
| `hitl_schema_migrations` | Runtime Store 表结构版本                               |
| `hitl_runs`              | 结构化状态/时间字段与完整 `RunRecord JSONB`            |
| `hitl_approvals`         | interrupt payload、pending/resolved 和人工决定 `JSONB` |
| `hitl_tool_results`      | 成功副作用 Tool 的幂等 `StepResult JSONB`              |

本地可用 DBeaver、TablePlus 或 pgAdmin 连接：Host `127.0.0.1`、Port `5432`、Database `obsidian_rag_v315`。Swagger 的 `GET /hitl/runtime` 只返回隐藏密码后的连接位置。

旧 `.rag-state/v3_15/*.sqlite3` 仅作为迁移源保留，不再被 V3.15 服务读取。一次性迁移命令：

```bash
.venv/bin/pip install -e '.[migration]'
.venv/bin/python scripts/migrate_v3_15_sqlite_to_postgres.py
```

## Swagger 调试

启动配置：`V3.15 API server: Recovery & HITL`，默认端口 `8024`。本仓库约定由学习者手动启动服务。

### 1. 触发审批

`POST /agent/ask`

```json
{
	"question": "请在隔离工作区创建 approval-demo.txt，内容为 V3.15 HITL 学习完成。",
	"conversation_id": "conv_v315_hitl",
	"principal": {
		"subject_id": "swagger_sandbox",
		"roles": ["user"],
		"permissions": [
			"knowledge.read",
			"tool.read",
			"sandbox.read",
			"sandbox.write",
			"sandbox.execute"
		],
		"tool_allowlist": ["search_notes", "sandbox::*"],
		"allowed_collections": ["*"]
	},
	"sandbox_enabled": true,
	"memory_window": 3,
	"top_k": 5,
	"mode": "hybrid",
	"max_steps": 4,
	"max_retries": 1,
	"context_max_chunks": 4,
	"context_token_budget": 4000
}
```

预期：

```json
{
	"run": { "status": "waiting_for_approval" },
	"approval": { "status": "pending" }
}
```

### 2. 查询审批

```text
GET /approvals/{run_id}
GET /approvals?status=pending
```

### 3. 允许并恢复

`POST /approvals/{run_id}/resume`

```json
{
	"action": "allow",
	"comment": "确认只写入当前 Run Workspace",
	"step_arguments": {}
}
```

### 4. 修改参数后恢复

```json
{
	"action": "edit",
	"comment": "修改输出文件名",
	"step_arguments": {
		"s1": {
			"path": "approved-result.txt",
			"content": "参数经过人工修改"
		}
	}
}
```

实际 `step_id` 以 `approval.request.steps` 返回值为准。

### 5. 拒绝

```json
{
	"action": "deny",
	"comment": "不允许本次文件写入",
	"step_arguments": {}
}
```

### 6. 恢复失败节点

如果 Run 为 `failed`，并且 Checkpoint 的 `next` 仍有待执行节点：

```text
POST /recoveries/{run_id}/retry
POST /recoveries/{run_id}/retry/stream
```

该操作传入 `None` 继续现有 thread，而不是重新提交原始问题，因此已经完成并写入 Checkpoint 的节点不会从头运行。

## CLI

触发审批：

```bash
.venv/bin/obsidian-rag agent-v3-15 ask \
  "请在隔离工作区创建 approval-demo.txt，内容为 V3.15 HITL 学习完成。" \
  --conversation-id conv_v315_hitl \
  --principal-profile sandbox \
  --json
```

恢复：

```bash
.venv/bin/obsidian-rag agent-v3-15 resume hitl_xxx \
  --action allow \
  --comment "允许执行"
```

恢复失败节点：

```bash
.venv/bin/obsidian-rag agent-v3-15 recover hitl_xxx
```

## 文件职责

| 文件                                                      | 作用                                                                     |
| --------------------------------------------------------- | ------------------------------------------------------------------------ |
| `obsidian_rag/v3_15/__init__.py`                          | 标记 V3.15 Python package                                                |
| `obsidian_rag/v3_15/app.py`                               | FastAPI app、路由组合和 Console 能力协商                                 |
| `obsidian_rag/v3_15/dependencies.py`                      | 创建 PostgresSaver、连接池、Store、Agent、Runtime 和复用的 V3.14 依赖    |
| `obsidian_rag/v3_15/postgres.py`                          | PostgreSQL DSN、脱敏连接信息和 psycopg ConnectionPool                    |
| `obsidian_rag/v3_15/agent.py`                             | `approval_gate`、interrupt/resume、Graph 编排和 Tool 幂等                |
| `obsidian_rag/v3_15/runtime.py`                           | Run 生命周期、waiting 状态、JSON/SSE 事件映射                            |
| `obsidian_rag/v3_15/store.py`                             | PostgreSQL Run、Approval、Tool Result、JSONB 和 Runtime Schema Migration |
| `obsidian_rag/v3_15/service.py`                           | API 使用的学习服务门面                                                   |
| `obsidian_rag/v3_15/schemas.py`                           | Swagger 可见的请求、审批、响应和运行配置契约                             |
| `obsidian_rag/v3_15/routes/agent.py`                      | 新建 JSON/SSE Agent Run                                                  |
| `obsidian_rag/v3_15/routes/approvals.py`                  | 查询审批、JSON/SSE resume                                                |
| `obsidian_rag/v3_15/routes/recoveries.py`                 | 失败节点 JSON/SSE Checkpoint retry                                       |
| `obsidian_rag/v3_15/routes/runtime.py`                    | Checkpoint 与恢复能力摘要                                                |
| `obsidian_rag/v3_15/routes/health.py`                     | Checkpoint、Runtime Store、Sandbox 和 MCP 健康摘要                       |
| `obsidian_rag/v3_15/routes/__init__.py`                   | 标记 V3.15 routes package                                                |
| `frontend/agent_console/src/components/ApprovalPanel.vue` | 审批步骤、参数编辑和 allow/deny/edit 操作                                |
| `scripts/migrate_v3_15_sqlite_to_postgres.py`             | 将旧 SQLite Runtime 与 Checkpoint 幂等迁移到 PostgreSQL                  |

## 核心断点调试

按真实执行顺序：

| 顺序 | 文件与位置                                  | 函数                        | 观察变量                                     |
| ---- | ------------------------------------------- | --------------------------- | -------------------------------------------- |
| 1    | `obsidian_rag/v3_15/routes/agent.py:13`     | `ask()`                     | `request.principal`、`request.question`      |
| 2    | `obsidian_rag/v3_15/runtime.py:27`          | `HitlRuntimeService.ask()`  | `run_id`、`record.status`                    |
| 3    | `obsidian_rag/v3_15/agent.py:105`           | `HitlAgentService.begin()`  | 初始 `AgentState`、`thread_id`               |
| 4    | `obsidian_rag/core/agent/service.py:796`    | `_authorize_steps_node()`   | `permission_report.confirm_count`            |
| 5    | `obsidian_rag/v3_15/agent.py:210`           | `_approval_gate_node()`     | `confirm_decisions`、`ApprovalRequest`       |
| 6    | `obsidian_rag/v3_15/agent.py:237`           | `interrupt()`               | interrupt payload、`run_id`                  |
| 7    | `obsidian_rag/v3_15/routes/approvals.py:37` | `resume()`                  | `run_id`、`request.action`                   |
| 8    | `obsidian_rag/v3_15/agent.py:116`           | `HitlAgentService.resume()` | `snapshot.interrupts`、`Command(resume=...)` |
| 9    | `obsidian_rag/v3_15/agent.py:271`           | `_report_after_decision()`  | 更新后的 Plan、PermissionDecision            |
| 10   | `obsidian_rag/v3_15/agent.py:310`           | `_execute_tool_step()`      | `idempotency_key`、`cached`                  |
| 11   | `obsidian_rag/core/agent/service.py:698`    | `_execute_steps_node()`     | `step_results`、Tool Observation             |
| 12   | `obsidian_rag/v3_15/runtime.py:174`         | `_complete()`               | waiting/succeeded 到 RunRecord 的映射        |
| 13   | `obsidian_rag/v3_15/agent.py:134`           | `recover()`                 | `snapshot.next`、失败节点 Checkpoint         |

代码变化后，行号可能移动，应优先用函数名重新定位。

## 建议掌握的问题

完成 V3.15 后，应能回答：

1. `interrupt()` 与普通异常有什么区别？
2. 为什么 `run_id` 与 LangGraph `thread_id` 在本版保持一致？
3. Conversation Memory、Run Store 和 Checkpoint 分别保存什么？
4. 为什么恢复执行仍然需要 Tool 幂等？
5. `deny` 为什么不是让整个 Graph 直接 500？
6. `checkpoints/checkpoint_blobs/checkpoint_writes` 与 `hitl_*` 表分别解决什么问题？

## 时序图

```mermaid
%%{init: {
  "themeVariables": {
    "fontSize": "18px"
  },
  "sequence": {
    "actorFontSize": 20,
    "messageFontSize": 18,
    "noteFontSize": 18,
    "messageMargin": 42,
    "boxTextMargin": 8
  }
}}%%
sequenceDiagram
    autonumber
    actor User as 用户 / 前端
    participant API as FastAPI
    participant Runtime as AgentRuntime
    participant Graph as LangGraph
    participant Policy as Permission Policy
    participant Gate as approval_gate
    participant CP as Checkpoint DB
    participant Store as Runtime Store
    participant Tool as Tool Executor
    participant LLM as Answer LLM

    User->>API: POST /ask
    API->>Runtime: ask_agent(request)
    Runtime->>Graph: ainvoke(initial_state)

    Graph->>Graph: load_memory
    Graph->>Graph: planner
    Graph->>Graph: select_skill
    Graph->>Policy: authorize_steps

    loop 检查每个 PlanStep
        Policy->>Policy: allow / confirm / deny
    end

    Policy-->>Graph: PermissionReport
    Graph->>Gate: approval_gate(state)

    alt 全部 allow
        Gate-->>Graph: 继续执行
        Graph->>Tool: execute_steps
        Tool-->>Graph: StepResult
        Graph->>Graph: evidence_check
        Graph->>LLM: synthesize_answer
        LLM-->>Graph: 最终答案
        Graph->>Graph: save_memory
        Graph-->>Runtime: completed state
        Runtime-->>API: ProductionAskResponse
        API-->>User: 200 JSON / SSE 终态

    else 存在 deny
        Gate-->>Graph: 拒绝对应步骤
        Graph->>Graph: 生成拒绝结果
        Graph->>LLM: synthesize_answer
        LLM-->>Graph: 安全说明或部分答案
        Graph-->>Runtime: completed state
        Runtime-->>API: Response
        API-->>User: 返回拒绝原因

    else 存在 confirm
        Gate->>CP: 保存 Graph Checkpoint
        Gate->>Store: 保存 Pending Approval
        Gate-->>Graph: interrupt()
        Graph-->>Runtime: waiting_for_approval
        Runtime-->>API: Pending Approval
        API-->>User: 显示审批面板

        User->>API: allow / deny / edit
        API->>Runtime: resume(run_id, decision)
        Runtime->>Store: 保存审批决定
        Runtime->>Graph: Command(resume=decision)
        Graph->>CP: 加载暂停现场
        CP-->>Graph: AgentState + next node

        Graph->>Gate: 从 interrupt() 后恢复

        alt allow
            Gate-->>Graph: 允许执行
            Graph->>Tool: execute_steps
        else edit
            Gate->>Graph: 使用修改后的 arguments
            Graph->>Tool: execute_steps
        else deny
            Gate-->>Graph: 生成 denied StepResult
        end

        Tool->>Store: 查询幂等执行结果

        alt 已执行过
            Store-->>Tool: 返回历史 Tool Result
        else 未执行
            Tool->>Tool: 调用真实 Tool
            Tool->>Store: 保存幂等结果
        end

        Tool-->>Graph: StepResult
        Graph->>Graph: evidence_check
        Graph->>LLM: synthesize_answer
        LLM-->>Graph: 最终答案
        Graph->>Graph: save_memory
        Graph-->>Runtime: completed state
        Runtime-->>API: Response
        API-->>User: 最终答案与执行信息
    end
```

## SVG 图解索引

- [HITL 暂停与恢复简化时序](assets/rag-v3-15-hitl-sequence-simple.svg)
- [详细 HITL 架构图](assets/rag-v3-15-hitl-flow.svg)
- [三类状态](assets/rag-v3-15-state-layers.svg)
- [恢复与幂等](assets/rag-v3-15-resume-idempotency.svg)
