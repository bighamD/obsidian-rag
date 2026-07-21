# AgentService 与 Tool Registry 复习指南

本文用于复习 V3.13 中 `PermissionAwareAgentService` 的继承与组合关系，以及
Core Skill Router、`ToolRegistry`、`planner_tools` 从加载到实际运行的完整链路。

## 1. 先记住结论

```text
继承关系负责复用 Agent 行为。
依赖组合负责启用 Collection Router、Permission Policy、Memory 等能力。

ToolRegistry 供 Policy 和 Executor 使用，包含工具实现和完整定义。
planner_tools 供 LLM Planner 使用，只包含安全、精简的工具说明。
```

`search_notes` 虽然存在于 `ToolRegistry`，但不进入 `planner_tools`。它是 Agent 固定的
`kind="search"` 内建能力；MCP Tool 是运行时才能发现的动态能力，因此通过
`planner_tools` 提供给 Planner，并生成 `kind="tool"` 步骤。

## 2. AgentService 继承关系

```text
obsidian_rag.core.agent.service.AgentService
    ↑
obsidian_rag.v3_12_3.agent.McpAgentService
    ↑
obsidian_rag.v3_12_4.agent.RoutedMcpAgentService
    ↑
obsidian_rag.v3_13.agent.PermissionAwareAgentService
```

### 2.1 Core AgentService

文件：`obsidian_rag/core/agent/service.py`

公共 `AgentService` 提供完整 Agent 主流程：

```text
load_memory
→ compact_memory
→ planner
→ resolve_retrieval_scope（注入 Resolver 时存在）
→ authorize_steps（注入 Permission Policy 时存在）
→ execute_steps
→ evidence_check
→ retry_search / build_context
→ synthesize_answer
→ save_memory
```

构造函数接收的关键依赖：

| 依赖 | 作用 |
| --- | --- |
| `retrieval_service` | 执行单库或多库检索、Reranking |
| `tool_registry` | 保存完整 Tool Definition 和执行函数 |
| `retrieval_scope_resolver` | 解析本轮允许检索的 Collection 范围 |
| `permission_policy` | 对 Planner 步骤生成 `allow/confirm/deny` 决策 |
| `memory_store` | 读取和保存 Conversation Turn |
| `chat_client_factory` | 为 Planner、Answer 和 Memory Compaction 创建 LLM Client |

Core 根据依赖是否为空决定是否把可选节点加入 LangGraph：

```python
if self.retrieval_scope_resolver is not None:
    graph.add_node("resolve_retrieval_scope", ...)

if self.permission_policy is not None:
    graph.add_node("authorize_steps", ...)
```

因此，版本能力并不完全由子类覆盖方法决定，也由构造时注入的组件决定。

### 2.2 McpAgentService

文件：`obsidian_rag/v3_12_3/agent.py`

`McpAgentService` 继承 Core Agent，增加动态工具选择和 Tool Observation：

- 保存 `planner_tools`。
- 把当前请求允许的 Tool Catalog 传给 Planner。
- 执行 `kind="tool"` 的计划步骤。
- 把工具结果转换为 `ToolObservation`。
- 在 Evidence 和 Answer 阶段考虑 Tool Observation。

主要覆盖方法：

```text
__init__
_initial_state
_planner_node
_execute_steps_node
_execute_tool_step
_evidence_check_node
_synthesize_answer_node
```

### 2.3 RoutedMcpAgentService

文件：`obsidian_rag/v3_12_4/agent.py`

当前类本身没有覆盖方法：

```python
class RoutedMcpAgentService(McpAgentService):
    """组合 MCP Tool Selection 与 Core RetrievalScopeResolver 的完整 Agent。"""
```

V3.12.4 的 Collection Router 能力来自依赖注入：

```python
retrieval_scope_resolver=get_collection_scope_resolver()
```

Core Agent 检测到 Resolver 后，自动加入 `resolve_retrieval_scope` 节点。

### 2.4 PermissionAwareAgentService

文件：`obsidian_rag/v3_13/agent.py`

当前类同样没有覆盖方法：

```python
class PermissionAwareAgentService(RoutedMcpAgentService):
    """在 V3.12.4 完整 Agent 上注入 Core Permission Policy。"""
```

V3.13 权限能力来自：

```python
permission_policy=get_permission_policy()
```

Core Agent 检测到 Policy 后，自动加入 `authorize_steps` 节点。

所以它的定位是：

```text
版本语义类型 + 依赖组合入口
```

## 3. V3.13 的组合关系

组装入口：`obsidian_rag/v3_13/dependencies.py::build_agent()`。

```text
PermissionAwareAgentService
├── CoreSkillResolver
├── RerankingRetrievalService
├── CollectionScopeResolver
├── StaticPermissionPolicy
├── ToolRegistry
├── planner_tools
├── OpenAIChatClient factory
└── Conversation MemoryStore
```

Skill Resolver 注入后，Core Graph 会在 Planner 前增加：

```text
discover_skills → skill_router → load_skill → planner
```

Skill 只提供 Planner 方法上下文，不直接执行动作；Planner 产生的 `search/tool` 仍统一经过 Permission Policy。

对应构造代码：

```python
PermissionAwareAgentService(
    retrieval_service=retrieval,
    retrieval_scope_resolver=get_collection_scope_resolver(),
    permission_policy=get_permission_policy(),
    tool_registry=registry,
    planner_tools=planner_tools,
    chat_client_factory=...,
    memory_store=get_memory_store(),
)
```

`McpAgentService.__init__()` 先保存：

```python
self.planner_tools = planner_tools
```

然后调用 Core `AgentService.__init__()`，保存 Registry、Resolver、Policy 等组件并构建 Graph。

## 4. ToolRegistry 与 planner_tools 的区别

### 4.1 ToolRegistry

类型：`obsidian_rag.core.tools.ToolRegistry`

它保存两组内部数据：

```text
_tools       工具名 → Python/MCP 调用函数
_definitions 工具名 → 完整 ToolDefinition
```

完整 `ToolDefinition` 包含：

```text
name
description
input_schema
read_only
source
risk_level
required_permission
scope
```

主要使用者：

```text
Permission Policy：读取风险、权限、Schema 和 scope
Tool Executor：根据工具名找到 handler 并执行
```

### 4.2 planner_tools

类型：`list[PlannerToolDefinition]`

只保存允许提供给 LLM 的精简信息：

```text
name
description
input_schema
source
read_only
```

它不包含：

- Python handler。
- MCP Session。
- API Key 或连接凭据。
- 最终 Permission Decision。
- `required_permission` 等内部执行策略。

主要使用者：

```text
LLM Planner：了解当前有哪些动态工具以及如何构造 arguments
```

### 4.3 二者关系

```text
同一个动态 Tool
├── 完整版本注册到 ToolRegistry
└── 精简版本追加到 planner_tools
```

Planner 能看到某个工具，不代表一定能执行。Planner 生成计划后，Permission Policy 仍会使用
`ToolRegistry` 中的完整定义重新检查。

## 5. Tool 数据来源与加载流程

V3.13 当前 Tool 大致来自三类来源：

```text
固定本地 Tool
└── search_notes

MCP 动态 Tool
├── demo::get_server_time
└── demo::lookup_food_temperature

V3.13 教学 Tool
└── local::simulate_workspace_write
```

### 5.1 MCP Server 配置加载

配置文件：`mcp_servers.yaml`

```text
FastAPI lifespan
→ get_mcp_connection_manager()
→ load_mcp_server_registry()
→ 读取并校验 mcp_servers.yaml
→ 创建 McpConnectionManager
→ manager.start()
→ 连接启用的 MCP Server
→ initialize
→ tools/list
→ 缓存远端 Tool Definition
```

相关文件：

| 文件 | 职责 |
| --- | --- |
| `obsidian_rag/v3_13/app.py` | 在 FastAPI lifespan 启动和停止 Manager |
| `obsidian_rag/v3_12_3/config.py` | 加载 `mcp_servers.yaml` |
| `obsidian_rag/v3_12_3/connection.py` | 管理持久 MCP Session、刷新和调用 Tool |
| `mcp_servers.yaml` | 声明 Server、Transport、allowlist 和缓存参数 |

### 5.2 每次 Agent 构造时注册 Tool

`StreamingAgentRuntimeService` 保存的是 `agent_factory=build_agent`。每次创建 Agent 时，调用：

```text
build_agent()
→ build_permission_agent_tool_registry()
→ build_agent_tool_registry()
```

MCP Manager 和 Session 可以跨请求复用，但 `ToolRegistry` 与 `planner_tools` 会根据当前已发现的
Tool Catalog 重新构造。

### 5.3 注册 search_notes

`build_agent_tool_registry()` 首先调用：

```python
registry = build_search_tool_registry(retrieval_service)
```

`build_search_tool_registry()` 注册：

```python
registry.register(
    "search_notes",
    search_notes,
    ToolDefinition(...),
)
```

这一步只把它注册到 `ToolRegistry`，不会追加到 `planner_tools`。

### 5.4 注册 MCP Tool

随后执行：

```python
remote_tools, errors = manager.list_tools()
```

对每个远端 Tool 做两件事：

```text
1. 构造 call_mcp handler 并注册到 ToolRegistry
2. 构造 PlannerToolDefinition 并追加到 planner_tools
```

注册后的 handler 最终调用：

```text
registry.run("demo::get_server_time")
→ call_mcp(...)
→ manager.call_tool(...)
→ 对应 MCP Session
→ tools/call
```

`planner_tools` 还受到以下配置限制：

```yaml
max_planner_tools: 24
max_tool_schema_chars: 12000
```

Registry 可以持有更多工具，但 Planner Catalog 会限制数量和 Schema 总长度，避免 Prompt 无限膨胀。

### 5.5 注册 V3.13 教学 Tool

`build_permission_agent_tool_registry()` 在 V3.12.3 Registry 基础上增加：

```text
local::simulate_workspace_write
```

它同时执行：

```python
registry.register(...)
planner_tools.append(...)
```

这个工具声明为：

```text
risk_level = confirm
required_permission = tool.write
read_only = false
```

它只模拟写入，不会真正修改磁盘，用来学习 `confirm` 决策。

## 6. 为什么 search_notes 不在 planner_tools

Planner Prompt 已经固定定义：

```text
kind="search"：查询本地知识库，必须提供 query
kind="tool"：从 user payload 的 tools 中选择动态工具
```

因此知识库检索计划是：

```json
{
  "id": "s1",
  "kind": "search",
  "query": "生鸡肉 清洗 交叉污染"
}
```

而 MCP 调用计划是：

```json
{
  "id": "s1",
  "kind": "tool",
  "tool_name": "demo::get_server_time",
  "arguments": {
    "timezone": "Asia/Shanghai"
  }
}
```

`search_notes` 不进入 `planner_tools` 的原因不是 Planner 不关心检索，而是它已作为固定的
`search` 能力写入 Planner 协议。

如果再把 `search_notes` 暴露为通用 Tool，LLM 会同时看到两种表达：

```text
kind="search"
kind="tool" + tool_name="search_notes"
```

这会产生重复入口，可能绕开 Collection Router、Retry Search、Evidence Checker 等专用检索语义。

## 7. 请求运行时的数据链

### 7.1 Planner 阶段

```text
McpAgentService._planner_node()
→ _catalog_for_request(request)
→ 从 self.planner_tools 生成当前请求 Catalog
→ 写入 AgentState.tool_catalog
→ PlanRequest(tools=catalog)
→ Planner 构造 Prompt
→ LLM 生成结构化 Plan
```

`_catalog_for_request()` 会根据请求参数过滤：

```text
mcp_enabled=false
→ 不向 Planner 提供动态 Tool Catalog

mcp_tool_names 非空
→ 只保留请求显式选择的 Tool
```

注意：V3.13 的 `local::simulate_workspace_write` 也存放在 `planner_tools` 中，因此当前关闭
`mcp_enabled` 时，它也不会提供给 Planner。这是学习版本复用同一 Catalog 开关的简化设计。

### 7.2 Collection 路由阶段

```text
Plan 中存在 kind="search"
→ resolve_retrieval_scope
→ CollectionScopeResolver
→ 显式 Collection / 默认 Collection / LLM Collection Router
→ AgentState.retrieval_scope
```

没有 `search` 步骤时，Scope 状态为 `not_required`。

### 7.3 Permission 阶段

```text
authorize_steps
→ 读取 request.principal
→ 遍历 Plan.steps
→ 从 ToolRegistry 查完整 ToolDefinition
→ 检查 allowlist、required permission、Collection scope、JSON Schema、risk
→ 生成 PermissionReport
```

`search` 步骤会映射到固定工具 `search_notes`。`tool` 步骤则使用 `step.tool_name`。

### 7.4 Executor 阶段

```text
execute_steps
├── Permission 为 confirm/deny
│   └── 生成 blocked StepResult，不执行 Tool
├── step.kind == "search"
│   └── registry.run("search_notes", ...)
├── step.kind == "tool"
│   └── registry.run(step.tool_name, **step.arguments)
└── 其他步骤
    └── 生成非工具 StepResult
```

因此最关键的职责分界是：

```text
planner_tools 决定 LLM 能规划哪些动态工具。
ToolRegistry 决定系统能检查和执行哪些工具。
Permission Policy 决定本轮主体是否真的允许执行。
```

## 8. 完整流程图

```text
mcp_servers.yaml
      ↓
load_mcp_server_registry
      ↓
McpConnectionManager.start
      ↓
initialize + tools/list
      ↓
远端 Tool Definition 缓存
      ↓
build_permission_agent_tool_registry
      ├── build_search_tool_registry
      │      └── Registry: search_notes
      ├── manager.list_tools
      │      ├── Registry: MCP handler + 完整定义
      │      └── planner_tools: MCP 精简定义
      └── V3.13 教学 Tool
             ├── Registry: simulate handler + 完整定义
             └── planner_tools: simulate 精简定义
      ↓
PermissionAwareAgentService
      ├── self.tool_registry
      └── self.planner_tools
      ↓
Planner 读取 planner_tools
      ↓
Plan: search / tool / synthesize / no_search / clarify
      ↓
CollectionScopeResolver（search 时）
      ↓
Permission Policy 读取 ToolRegistry Definition
      ↓
allow / confirm / deny
      ↓
Executor 通过 ToolRegistry.run 执行 allow 步骤
```

## 9. 推荐断点

代码变化后优先按函数名重新定位，不要只依赖行号。

| 顺序 | 文件 | 函数 | 重点观察 |
| --- | --- | --- | --- |
| 1 | `obsidian_rag/v3_13/app.py` | `lifespan` | `manager`、MCP 启停时机 |
| 2 | `obsidian_rag/v3_12_3/config.py` | `load_mcp_server_registry` | `registry_path`、解析后的 Server 配置 |
| 3 | `obsidian_rag/v3_12_3/connection.py` | `McpConnectionManager.list_tools` | `server.tools`、`definitions`、`errors` |
| 4 | `obsidian_rag/v3_13/dependencies.py` | `build_agent` | `registry.list_tools()`、`planner_tools` |
| 5 | `obsidian_rag/v3_12_3/registry.py` | `build_agent_tool_registry` | Local Registry、`remote_tools`、Catalog 限制 |
| 6 | `obsidian_rag/v3_13/registry.py` | `build_permission_agent_tool_registry` | simulate Tool 两处注册 |
| 7 | `obsidian_rag/v3_12_3/agent.py` | `McpAgentService.__init__` | `self.planner_tools` 与传给 Core 的 Registry |
| 8 | `obsidian_rag/core/agent/service.py` | `AgentService.__init__` | Resolver、Policy 是否注入，Graph 构建条件 |
| 9 | `obsidian_rag/v3_12_3/agent.py` | `_planner_node` | `catalog`、`PlanRequest.tools`、最终 `plan` |
| 10 | `obsidian_rag/core/agent/service.py` | `_resolve_retrieval_scope_node` | `search_required`、`retrieval_scope` |
| 11 | `obsidian_rag/core/agent/service.py` | `_authorize_steps_node` | `principal`、Registry、`permission_report` |
| 12 | `obsidian_rag/v3_12_3/agent.py` | `_execute_steps_node` | blocked、search、tool 三类分支 |
| 13 | `obsidian_rag/core/agent/service.py` | `_execute_search_step` | `registry.run("search_notes")` 参数与结果 |
| 14 | `obsidian_rag/v3_12_3/agent.py` | `_execute_tool_step` | `step.tool_name`、`ToolResult`、`ToolObservation` |

## 10. 复习问题

1. 为什么 `PermissionAwareAgentService` 没有覆盖方法，仍然能增加 `authorize_steps`？
2. 为什么 `search_notes` 在 Registry 中，却不在 `planner_tools` 中？
3. Planner 看到一个 Tool 后，为什么仍不能保证它会执行？
4. `mcp_servers.yaml`、MCP `tools/list`、Registry 注册分别发生在什么阶段？
5. 为什么 Registry 可以比 Planner Catalog 包含更多工具？
6. `kind="search"` 和 `kind="tool"` 最终分别在哪个函数进入 Executor？

参考答案：

```text
1. Core 根据注入的 permission_policy 动态构建 Graph。
2. search_notes 是内建 search 能力，planner_tools 只描述动态 tool 能力。
3. 还要经过 Tool allowlist、权限、scope、Schema 和 risk 检查。
4. 配置在 Manager 构造时加载，tools/list 在 Manager 启动/刷新时发生，Registry 在 Agent 构造时注册。
5. Planner Catalog 需要控制 Prompt 大小，并且不是所有可执行工具都应暴露给当前请求。
6. search 进入 _execute_search_step，tool 进入 _execute_tool_step。
```
