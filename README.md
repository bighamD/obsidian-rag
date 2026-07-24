# Obsidian RAG v0

本项目是一个本地运行的 RAG v0 学习项目，面向 Obsidian Markdown 和 PDF 文档。

不知道各版本分别做什么时，先看：[版本能力矩阵](docs/version-capability-matrix.md)。

当前主线版本 V3.12.4：[Unified Knowledge Routing Guide](docs/v3-12-4-unified-knowledge-routing-guide.md)。

学习路线和 v0-v4 计划见：[docs/rag-roadmap.md](docs/rag-roadmap.md)。

源码职责、架构图和时序图见：[docs/obsidian-rag-code-guide.md](docs/obsidian-rag-code-guide.md)。

V1 混合检索、FastAPI 接口和每个 V1 文件职责见：[docs/v1-hybrid-search-guide.md](docs/v1-hybrid-search-guide.md)。

V2 评估集、检索指标、答案指标和每个 V2 文件职责见：[docs/v2-evaluation-guide.md](docs/v2-evaluation-guide.md)。

V3 轻量 Agentic RAG、trace、Swagger 和每个 V3 文件职责见：[docs/v3-agentic-rag-guide.md](docs/v3-agentic-rag-guide.md)。

V3.1 LLM Router、结构化 JSON 路由、Swagger 和每个 V3.1 文件职责见：[docs/v3-1-llm-router-guide.md](docs/v3-1-llm-router-guide.md)。

V3.2 Tool Calling、`search_notes/no_search/clarify` 工具选择、Swagger 和每个 V3.2 文件职责见：[docs/v3-2-tool-calling-guide.md](docs/v3-2-tool-calling-guide.md)。

V3.3 LangGraph、节点编排、`graph_path` 和每个 V3.3 文件职责见：[docs/v3-3-langgraph-guide.md](docs/v3-3-langgraph-guide.md)。

V3.4 Planner、LangGraph planner nodes、结构化 `Plan JSON`、Swagger 和每个 V3.4 文件职责见：[docs/v3-4-planner-guide.md](docs/v3-4-planner-guide.md)。

V3.5 Planner Executor、`ToolRegistry`、`StepResult`、Swagger 和每个 V3.5 文件职责见：[docs/v3-5-planner-executor-guide.md](docs/v3-5-planner-executor-guide.md)。

V3.11.3 Knowledge Base Registry、Collection Router、多库 Hybrid Retrieval 和跨库 RRF 见：[docs/v3-11-3-collection-router-guide.md](docs/v3-11-3-collection-router-guide.md)。

V3.12 MCP Client/Server、`tools/list`、`tools/call`、Tool Schema Adapter 和 RAG MCP Server 见：[docs/v3-12-mcp-integration-guide.md](docs/v3-12-mcp-integration-guide.md)。

V3.12.1 公共 Agent Core、统一 Tool Registry、`answer_delta` SSE 和前端增量答案见：[docs/v3-12-1-agent-core-streaming-guide.md](docs/v3-12-1-agent-core-streaming-guide.md)。

VSCode/Cursor 调试 RAG 流程见：[docs/debugging-rag-flow.md](docs/debugging-rag-flow.md)。

配套学习图片见：[docs/assets](docs/assets)。

v0 目标：

- 扫描本地 Markdown/PDF
- 提取 Obsidian 常见元数据：frontmatter、标题、标签、双链
- 将文档切成 chunks
- 调用 embedding provider 生成向量；当前 cliproxy 无 embeddings endpoint，下一步优先接本地 Ollama embedding
- 写入 Docker Qdrant 向量库；未配置 `QDRANT_URL` 时可退回 embedded 本地库
- 支持纯检索 `search`
- 支持检索后调用 LLM 回答 `ask`
- 输出来源文件

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

编辑 `.env`：

```bash
OPENAI_API_KEY=你的本地 cliproxy key
OPENAI_BASE_URL=http://127.0.0.1:8317/v1
RAG_CHAT_MODEL=gpt-5.4-mini
RAG_EMBED_MODEL=qwen3-embedding:0.6b
RAG_EMBED_DIMENSIONS=1024
RAG_EMBED_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
RAG_VAULT_PATH=/你的/ObsidianVault/路径
QDRANT_URL=http://127.0.0.1:6333
RAG_COLLECTION=obsidian_notes
RAG_MIN_SCORE=0.35
```

如果你的 cliproxy 使用了不同模型名，把 `RAG_CHAT_MODEL` 改成它实际支持的名称。

注意：当前已验证 cliproxy 的 `/v1/embeddings` 不可用，所以 embedding 默认走本地 Ollama。当前配置使用 `qwen3-embedding:0.6b`，向量维度是 `1024`。

Qdrant 默认连接 Docker 服务：

```bash
QDRANT_URL=http://127.0.0.1:6333
```

如果不设置 `QDRANT_URL`，才会退回 embedded 本地文件库 `RAG_DB_PATH=.rag/qdrant`。完整路线见 [docs/rag-roadmap.md](docs/rag-roadmap.md)。

`RAG_MIN_SCORE` 是 `ask` 的相关性门槛。`search` 会继续展示 top-k 结果和分数；`ask` 如果最高分低于这个阈值，会拒绝把不相关 chunk 发给 LLM 硬答。

## Index Your Vault

先确保 Docker Qdrant 已启动：

```bash
docker start rag-qdrant
```

```bash
.venv/bin/obsidian-rag ingest --recreate
```

`ingest` 不传路径时会读取 `.env` 里的 `RAG_VAULT_PATH`。

### 多知识库 Collection

`RAG_COLLECTION` 是默认知识库。单次 ingest、search 或 ask 可以用 `--collection` 覆盖它；`collection` 是物理检索边界，`category` / `tags` 仍是库内 metadata。名称必须匹配 `^[a-z0-9][a-z0-9_-]{0,62}$`，例如 `food_safety`、`recipes`。

```bash
# 食品安全资料
.venv/bin/obsidian-rag ingest /path/to/food-safety --collection food_safety --recreate

# 菜谱资料
.venv/bin/obsidian-rag ingest /path/to/recipes --collection recipes --recreate

# 仅在指定知识库中检索
.venv/bin/obsidian-rag search "生鸡肉需要清洗吗？" --collection food_safety
.venv/bin/obsidian-rag ask "番茄意面怎么做？" --collection recipes
```

每个 collection 有独立的 Qdrant collection 和 keyword index（默认 `RAG_DB_PATH=.rag/qdrant` 时）：

```text
.rag/keyword_indexes/food_safety.json
.rag/keyword_indexes/recipes.json
```

旧 `.rag/keyword_index.json` 不会自动迁移；首次切换到多 collection 后，需要对每个知识库执行一次 `ingest --collection ... --recreate`。`--recreate` 只会全量重建指定 collection；省略它时，新 chunks 会增量写入当前 collection 并合并 keyword index。当前一个 `conversation_id` 应只用于一个 collection，避免 Memory 带入另一知识库的历史上下文；这是调用约定，尚未做运行时隔离校验。

也可以用命令行路径临时覆盖配置：

```bash
.venv/bin/obsidian-rag ingest "/path/to/other/ObsidianVault" --recreate
.venv/bin/obsidian-rag ingest "/path/to/note.md" --recreate
.venv/bin/obsidian-rag ingest "/path/to/file.pdf" --recreate
```

## Search Only

先用 `search` 看 RAG 到底捞出了什么，不调用 LLM：

```bash
.venv/bin/obsidian-rag search "我关于 Agent memory 写过什么？" --top-k 5
```

这一步最适合调试 chunk 大小、标签、来源和召回质量。

## Ask With LLM

```bash
.venv/bin/obsidian-rag ask "我关于 Agent memory 写过什么？" --top-k 5
```

`ask` 会做：

```text
问题 -> embedding -> Qdrant 检索 -> 拼 RAG prompt -> LLM 回答 -> 输出 sources
```

## V1 FastAPI

V1 增加了 FastAPI JSON 接口和 Swagger 调试页面，代码放在 `obsidian_rag/v1/`。

如果想理解 V1 比 V0 改进了什么、hybrid search 如何融合 dense 和 keyword，以及 `obsidian_rag/v1/` 每个文件的作用，先看：[docs/v1-hybrid-search-guide.md](docs/v1-hybrid-search-guide.md)。

启动 API：

```bash
.venv/bin/uvicorn obsidian_rag.v1.app:app --reload
```

打开 Swagger：

```text
http://127.0.0.1:8000/docs
```

当前接口：

- `GET /health`
- `POST /ingest`
- `POST /search`
- `POST /compare-search`
- `POST /ask`

`/search` 支持 `dense`、`keyword`、`hybrid` 三种模式：

```json
{
  "query": "生鸡肉要不要洗",
  "top_k": 5,
  "mode": "hybrid",
  "collection": "food_safety"
}
```

`/compare-search` 会同时返回 dense、keyword、hybrid 三组结果，适合在 Swagger 里观察混合检索是否改善了召回。

`/ask` 当前只返回 JSON，不使用 SSE：

```json
{
  "question": "生鸡肉还需要清洗下锅吗",
  "top_k": 5,
  "mode": "hybrid",
  "collection": "food_safety"
}
```

注意：`keyword` 和 `hybrid` 依赖当前 collection 对应的 keyword index（默认路径为 `.rag/keyword_indexes/<collection>.json`）。运行 `obsidian-rag ingest --collection <collection> --recreate` 或调用 `POST /ingest` 后会自动生成。

## V2 Evaluation

V2 增加了可重复评估工作流，用固定评估集衡量检索质量。详细说明见：[docs/v2-evaluation-guide.md](docs/v2-evaluation-guide.md)。

运行示例检索评估：

```bash
.venv/bin/obsidian-rag eval retrieval eval_sets/retrieval-food-safety.yaml --top-k 5 --mode hybrid
```

启动 V2 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v2.app:app --reload --port 8001
```

打开：

```text
http://127.0.0.1:8001/docs
```

## V3 Agentic RAG

V3 增加轻量 Agentic RAG：agent 会判断是否需要检索、调用 `search_notes` 工具、必要时做第二次检索，并返回 trace。详细说明见：[docs/v3-agentic-rag-guide.md](docs/v3-agentic-rag-guide.md)。

启动 V3 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v3.app:app --reload --port 8002
```

打开：

```text
http://127.0.0.1:8002/docs
```

CLI 示例：

```bash
.venv/bin/obsidian-rag agent ask "生鸡肉要不要洗，处理完后厨房怎么清洁？" --top-k 5 --mode hybrid --max-steps 2
```

## V3.1 LLM Router

V3.1 把 V3 的规则判断升级成 LLM Router：模型先输出结构化 JSON，代码再根据 `search`、`no_search`、`clarify` 决定下一步。详细说明见：[docs/v3-1-llm-router-guide.md](docs/v3-1-llm-router-guide.md)。

启动 V3.1 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v3_1.app:app --reload --port 8003
```

打开：

```text
http://127.0.0.1:8003/docs
```

Swagger 示例：

```json
{
  "question": "今天深圳天气怎么样",
  "top_k": 5,
  "mode": "hybrid",
  "filters": null,
  "max_steps": 1
}
```

观察 `router.action`、`router.intent`、`used_retrieval` 和 `trace[0]`，可以判断 LLM Router 有没有正确识别用户意图。

## V3.2 Tool Calling

V3.2 把 V3.1 的 Router JSON 升级成模型原生 Tool Calling：模型直接选择 `search_notes`、`no_search` 或 `clarify`，代码执行工具并把 tool result 回传给模型。详细说明见：[docs/v3-2-tool-calling-guide.md](docs/v3-2-tool-calling-guide.md)。

启动 V3.2 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v3_2.app:app --reload --port 8004
```

打开：

```text
http://127.0.0.1:8004/docs
```

CLI 示例：

```bash
.venv/bin/obsidian-rag agent-v3-2 ask "生鸡肉还需要清洗下锅吗？" --top-k 5 --mode hybrid --max-steps 1
```

## V3.3 LangGraph

V3.3 把 V3.2 的 Tool Calling loop 拆成 LangGraph 节点：`select_tool`、`search_notes`、`evidence_check`、`answer`、`no_search`、`clarify`。详细说明见：[docs/v3-3-langgraph-guide.md](docs/v3-3-langgraph-guide.md)。

启动 V3.3 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v3_3.app:app --reload --port 8005
```

打开：

```text
http://127.0.0.1:8005/docs
```

CLI 示例：

```bash
.venv/bin/obsidian-rag agent-v3-3 ask "生鸡肉还需要清洗下锅吗？" --top-k 5 --mode hybrid --max-steps 1
```

## V3.4 Planner

V3.4 增加 planner-only LangGraph 流程：把复杂问题拆成结构化 `Plan JSON`，但暂时不执行检索步骤。详细说明见：[docs/v3-4-planner-guide.md](docs/v3-4-planner-guide.md)。

启动 V3.4 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v3_4.app:app --reload --port 8006
```

打开：

```text
http://127.0.0.1:8006/docs
```

CLI 示例：

```bash
.venv/bin/obsidian-rag agent-v3-4 plan "帮我总结生鸡肉处理、厨房清洁、剩菜保存三类食品安全建议" --top-k 5 --mode hybrid --max-steps 4
```

## V3.5 Planner Executor

V3.5 把 V3.4 的 `Plan JSON` 执行起来：`search` step 会调用本地知识库检索，最终基于 `step_results` 综合答案。详细说明见：[docs/v3-5-planner-executor-guide.md](docs/v3-5-planner-executor-guide.md)。

启动 V3.5 Swagger：

```bash
.venv/bin/uvicorn obsidian_rag.v3_5.app:app --reload --port 8007
```

打开：

```text
http://127.0.0.1:8007/docs
```

CLI 示例：

```bash
.venv/bin/obsidian-rag agent-v3-5 ask "帮我总结生鸡肉处理、厨房清洁、剩菜保存三类食品安全建议" --top-k 5 --mode hybrid --max-steps 4
```

## Offline Smoke Test

如果你只想验证本地索引和检索链路，不调用真实 embedding API，可以临时用 hash embedding：

```bash
RAG_EMBED_PROVIDER=hash RAG_EMBED_DIMENSIONS=64 .venv/bin/obsidian-rag ingest ./sample-notes --recreate
RAG_EMBED_PROVIDER=hash RAG_EMBED_DIMENSIONS=64 .venv/bin/obsidian-rag search "agent memory retrieval"
```

hash embedding 只适合开发自检，不代表真实语义检索质量。

## Tests

```bash
.venv/bin/python -m pytest
```
