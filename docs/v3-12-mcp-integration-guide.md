# V3.12 MCP Integration 学习指南

V3.12 学习 Harness 如何通过标准协议发现和调用外部工具，以及如何把已有 RAG 能力暴露给其他 MCP Client。

![V3.12 MCP Integration 流程](assets/rag-v3-12-mcp-integration-flow.svg)

## 相比 V3.11 新增了什么

V3.11 解决的是“采用什么工作方法”：

```text
Skill Registry -> Skill Router -> load SKILL.md -> Planner
```

V3.12 解决的是“通过什么标准协议发现和调用能力”：

```text
MCP Client -> initialize -> tools/list -> tools/call -> MCP Server
```

三个概念必须保持边界：

```text
Skill：告诉 Agent 如何完成一类任务
Tool：执行一个具体动作
MCP：规定 Tool 如何被发现、描述和调用
```

## 当前版本做什么

- 使用官方 Python `mcp` SDK。
- 使用 `stdio` Transport 启动本地 MCP Server。
- 支持 MCP `initialize`、`tools/list` 和 `tools/call`。
- 把 MCP Tool Schema 适配成稳定的本地 `McpToolDefinition`。
- 把 `CallToolResult` 适配成稳定的 `McpToolCallResponse`。
- 提供低风险 Demo MCP Server。
- 把本地 `search_notes` 和 `list_collections` 暴露为 RAG MCP Server。
- 记录 Server、Tool、协议阶段、状态和耗时，不记录 Secret。

## 当前版本不做什么

- 不让 LLM 自动选择 MCP Tool，本版先显式调用以学习协议边界。
- 不执行 Skill 目录下的 `scripts/`。
- 不开放宿主机 Shell、任意文件读写或网络代理。
- 不实现 `allow / confirm / deny`，该能力属于 V3.13 Permission Policy。
- 不实现隔离执行和 Artifacts，该能力属于 V3.14 Sandbox Execution。
- 不学习 MCP `resources`、`prompts`、Sampling 和生产级长连接池。
- 不新增 SSE，也不改 V3.11 Agent 主链路。

## 与 roadmap 的实现取舍

V3.12 已按学习节奏先完成独立 MCP 协议实验，因为 FastAPI 和 CLI 可以直接显式调用 MCP Tool，不依赖 Agent Core 迁移。roadmap 现已把 AgentRuntime/Core Extraction 调整为后续 V3.12.1。

本版已经建立 MCP Tool/Result 的稳定 Adapter，但暂不把 MCP Tool 注册进旧 V3.5 `ToolRegistry`，也不让 Planner/LLM 自动选择它。V3.12.1 将通过公共 Registry Adapter 接入，避免让新 MCP 层反向依赖某个旧学习版本目录。

## MCP 四个角色

| 角色 | 在本项目中的对应物 | 职责 |
| --- | --- | --- |
| Host | FastAPI、CLI 或未来 Agent Runtime | 发起任务并决定何时使用 MCP 能力 |
| Client | `McpClientManager` | 建立 Session，发送 MCP 请求并读取结果 |
| Server | `demo_server.py`、`rag_server.py` | 声明并执行具体 Tools |
| Session | `ClientSession` | 在一次连接中完成 initialize、list 和 call |

当前实现为了让生命周期容易观察，每次 API/CLI 调用都会创建一个短生命周期 stdio Session：

```text
启动子进程 -> initialize -> tools/list -> tools/call -> 关闭 Session 和子进程
```

因此首次调用通常有数百毫秒的进程启动成本。真实生产系统可以复用 Session，但必须额外处理断线、重连、并发和进程健康。

## 为什么先调用 tools/list

MCP Client 不应该在代码里假设远端工具参数。`tools/list` 返回：

- Tool 名称和描述。
- `inputSchema` 参数 JSON Schema。
- 可选 `outputSchema`。
- `readOnlyHint` 等 annotations。

V3.12 把远端 Schema 映射为：

```text
demo::lookup_food_temperature
rag::search_notes
```

`server::tool` 命名空间避免多个 Server 出现同名工具。注意 `readOnlyHint` 只是 Server 声明的提示，不是安全授权；V3.13 才会建立真正的 Policy Decision。

## tools/call 主链路

```text
POST /mcp/call
  -> McpIntegrationService.call_tool()
  -> McpClientManager.call_tool()
  -> stdio_client()
  -> ClientSession.initialize()
  -> ClientSession.list_tools()
  -> ClientSession.call_tool()
  -> adapt_content() / structured_content()
  -> McpToolCallResponse
```

调用前再次执行 `tools/list`，用于确认 Tool 仍然存在。学习版优先保证协议过程可见，没有实现 Tool Schema Cache。

## 两个 MCP Server

### Demo Server

提供：

- `lookup_food_temperature`
- `get_server_time`

这两个 Tool 都是低风险、只读工具，适合观察协议而不依赖 Qdrant 或 LLM。

### RAG Server

提供：

- `search_notes`：复用现有 `RetrievalService`，支持 dense、keyword、hybrid 和 collection。
- `list_collections`：读取 `knowledge_bases.yaml` 中启用的 Collection。

RAG Server 不提供 `ask_notes`，避免 MCP 协议学习混入 Answer LLM 的额外延迟。

## Swagger 调试

用户自主启动：

```bash
.venv/bin/uvicorn obsidian_rag.v3_12.app:app --host 127.0.0.1 --port 8019
```

打开：

```text
http://127.0.0.1:8019/docs
```

### 1. 查看 Server

```text
GET /mcp/servers
```

该接口只展示配置，不启动 MCP Server。

### 2. 发现 Demo Tools

```text
GET /mcp/tools?server_name=demo
```

该接口会启动 Demo MCP Server，完成 `initialize` 和 `tools/list`，随后关闭子进程。

### 3. 调用食品温度 Tool

```json
{
  "server_name": "demo",
  "tool_name": "lookup_food_temperature",
  "arguments": {
    "food": "chicken"
  }
}
```

### 4. 调用 RAG 检索 Tool

```json
{
  "server_name": "rag",
  "tool_name": "search_notes",
  "arguments": {
    "query": "生鸡肉要不要清洗？",
    "top_k": 5,
    "mode": "hybrid",
    "collection": "food_safety"
  }
}
```

### 5. 参数错误分支

```json
{
  "server_name": "demo",
  "tool_name": "lookup_food_temperature",
  "arguments": {}
}
```

MCP Server 会返回 Tool Error，FastAPI 仍返回结构化 `McpToolCallResponse`，其中 `status=failed`、`is_error=true`，而不是让整个 API 变成未处理的 500。

## CLI 调试

```bash
.venv/bin/obsidian-rag mcp-v3-12 servers
.venv/bin/obsidian-rag mcp-v3-12 tools --server demo
.venv/bin/obsidian-rag mcp-v3-12 call demo lookup_food_temperature --arguments '{"food":"chicken"}'
.venv/bin/obsidian-rag mcp-v3-12 call rag list_collections --arguments '{}'
```

如果要让其他 MCP Client 连接本项目：

```bash
.venv/bin/obsidian-rag mcp-v3-12 serve-rag
```

这是 stdio Server，不是普通 HTTP 服务；应由 MCP Client 以子进程方式启动，不能直接在浏览器中访问。

## 正常路径与条件分支

### 正常发现

```text
known server -> initialize success -> tools/list success -> adapted tools
```

### 未知 Server

```text
unknown server -> KeyError -> GET /mcp/tools 返回 404
```

### Server 启动失败或超时

```text
spawn/connect/initialize failure -> errors[server_name] + failed trace
```

遍历全部 Server 时，一个 Server 失败不会丢弃其他 Server 已发现的工具。

### 未知 Tool

```text
initialize -> tools/list -> tool missing -> failed McpToolCallResponse
```

### Tool 参数错误

```text
tools/call -> MCP CallToolResult.isError=true -> status=failed
```

### Tool 返回过大

`RAG_MCP_MAX_RESULT_BYTES` 默认是 `262144`。超过上限时只返回结构化失败和 trace，不把巨大 Content Blocks 送入 API 或未来 Agent Context。

## 文件职责

| 文件 | 作用 |
| --- | --- |
| `obsidian_rag/v3_12/app.py` | 组装 V3.12 FastAPI app |
| `obsidian_rag/v3_12/dependencies.py` | 注册 Demo/RAG Server 配置并创建 Service |
| `obsidian_rag/v3_12/schemas.py` | Swagger、Tool Schema、Call Result 和 Trace 契约 |
| `obsidian_rag/v3_12/client/manager.py` | stdio 子进程、ClientSession 和 MCP 协议生命周期 |
| `obsidian_rag/v3_12/client/adapter.py` | SDK Tool/Content 对象到本地 Schema 的转换 |
| `obsidian_rag/v3_12/service.py` | 多 Server 发现、显式调用和错误归一化 |
| `obsidian_rag/v3_12/routes/mcp.py` | `/mcp/servers`、`/mcp/tools`、`/mcp/call` |
| `obsidian_rag/v3_12/servers/demo_server.py` | 低风险测试 MCP Server |
| `obsidian_rag/v3_12/servers/rag_server.py` | 对外暴露本地 RAG 只读工具 |
| `tests/v3_12/` | Service、API、CLI 契约测试代码 |

## 核心断点调试

代码变化后行号可能移动，应优先按函数名重新定位。

### tools/list 执行顺序

| 顺序 | 断点 | 观察变量 |
| --- | --- | --- |
| 1 | `obsidian_rag/v3_12/routes/mcp.py:24 list_tools` | `server_name`、`service` |
| 2 | `obsidian_rag/v3_12/service.py:39 McpIntegrationService.list_tools` | `servers`、`tools`、`errors`、`trace` |
| 3 | `obsidian_rag/v3_12/client/manager.py:62 McpClientManager.discover_tools` | `server`、`server.timeout_seconds` |
| 4 | `obsidian_rag/v3_12/client/manager.py:102 McpClientManager._session` | `parameters.command`、`parameters.args`、`parameters.cwd` |
| 5 | `obsidian_rag/v3_12/client/manager.py:120 ClientSession.initialize` | `initialized.protocolVersion` |
| 6 | `obsidian_rag/v3_12/client/manager.py:67 ClientSession.list_tools` | `result.tools` |
| 7 | `obsidian_rag/v3_12/client/adapter.py:10 adapt_tool` | `tool.inputSchema`、`tool.annotations`、`namespaced_name` |

### tools/call 执行顺序

| 顺序 | 断点 | 观察变量 |
| --- | --- | --- |
| 1 | `obsidian_rag/v3_12/routes/mcp.py:35 call_tool` | `request.server_name`、`request.tool_name`、`request.arguments` |
| 2 | `obsidian_rag/v3_12/service.py:91 McpIntegrationService.call_tool` | `started`、`trace`、`protocol_call` |
| 3 | `obsidian_rag/v3_12/client/manager.py:75 McpClientManager.call_tool` | `listed.tools`、`tool` |
| 4 | `obsidian_rag/v3_12/client/manager.py:91 ClientSession.call_tool` | `tool_name`、`arguments`、`result.isError` |
| 5 | `obsidian_rag/v3_12/servers/demo_server.py:19 lookup_food_temperature` | `food`、`normalized`、`matched` |
| 6 | `obsidian_rag/v3_12/client/adapter.py:26 adapt_content` | `result.content`、`payload` |
| 7 | `obsidian_rag/v3_12/service.py:91` 返回前 | `status`、`structured_content`、`duration_ms`、`trace` |

`launch.json` 中的 V3.12 配置设置了 `subProcess=true`，便于调试 CLI/FastAPI 启动的 stdio MCP 子进程。

## 学习完成标准

- 能解释为什么 MCP Tool 不等于 Skill。
- 能画出 Host、Client、Session、Server 的关系。
- 能说明 `tools/list` 如何生成 Tool JSON Schema。
- 能调试一次完整 `initialize -> tools/list -> tools/call`。
- 能区分 Content Blocks 和 `structured_content`。
- 能说明 `readOnlyHint` 为什么不能替代 Permission Policy。
- 能使用外部 MCP Client 启动 `rag_server` 并调用 `search_notes`。

## 下一版本

V3.13 Permission Policy 将在本地 Tool 和 MCP Tool 进入执行器之前统一判断：

```text
Tool Call -> schema validation -> Policy Engine -> allow / confirm / deny -> Tool Executor
```

V3.13 仍不会直接开放任意 Shell；真正的隔离执行留到 V3.14 Sandbox Execution。
