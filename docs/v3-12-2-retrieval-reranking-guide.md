# V3.12.2 Retrieval Reranking 学习指南

## 版本定位

V3.12.2 插入在 V3.12.1 Agent Core 与 V3.13 Permission Policy 之间，专门学习检索质量链路：

```text
Dense + Keyword
    -> RRF / cross-collection RRF
    -> Parent collapse / expansion
    -> Reranker(query, matched child)
    -> rerank Top K
    -> ContextBuilder(returned parent)
    -> Answer LLM
```

本版本新增 CrossEncoder Reranker、fail-open、排序可观测性和离线对照评估。它不重新切片、不重新 Embedding、不迁移 Collection/keyword index，也不改变 V3.12.1 API。

下一版本回到既定主线：V3.13 Permission Policy。

## 为什么选 sentence-transformers + BGE

工具和模型需要分开理解：

- `sentence-transformers CrossEncoder` 是推理 Adapter，负责加载模型并批量计算 `query + document` 分数。
- `BAAI/bge-reranker-v2-m3` 是默认推荐模型，适合中文与多语言知识库。
- `none` 是现有 RRF baseline。
- `fake` 只用于离线单元测试，不下载模型。

本学习版没有直接采用 LangChain/LlamaIndex wrapper，因为项目已有 RetrievalService、ContextBuilder 和稳定 schemas，薄 Adapter 更容易观察真实输入输出。`FlagEmbedding` 更适合后续 BGE 专用高级模型；Cohere/Jina 更适合后续远端生产 Adapter。

如果本机 CPU/Mac 跑 `bge-reranker-v2-m3` 较慢，只修改 `RAG_RERANK_MODEL` 即可换成兼容的轻量 CrossEncoder，不需要修改检索主链路。

## 安装与配置

基础安装不会引入 PyTorch：

```bash
pip install -e .
```

启用真实本地模型时安装可选依赖：

```bash
pip install -e '.[rerank]'
```

推荐配置：

```env
RAG_RERANK_ENABLED=true
RAG_RERANK_PROVIDER=sentence_transformers
RAG_RERANK_MODEL=BAAI/bge-reranker-v2-m3
RAG_RERANK_CANDIDATES=20
RAG_RERANK_TOP_K=5
RAG_RERANK_TIMEOUT_SECONDS=10
RAG_RERANK_DEVICE=auto
RAG_RERANK_BATCH_SIZE=8
```

关闭真实重排并观察 RRF baseline：

```env
RAG_RERANK_ENABLED=false
```

## 启动方式

VS Code/Cursor 运行：

```text
V3.12.2 API server: Retrieval Reranking
Agent Console UI: console.v1 (V3.12.2)
```

或者手工启动：

```bash
.venv/bin/uvicorn obsidian_rag.v3_12_2.app:app --host 127.0.0.1 --port 8021
```

Swagger：`http://127.0.0.1:8021/docs`

## Swagger 调试案例

### 单 Collection 重排

`POST /rerank/search`

```json
{
  "query": "剩菜可以保存多久",
  "top_k": 5,
  "mode": "hybrid",
  "collection": "food_safety"
}
```

响应重点观察：

```text
run.provider / model / latency_ms / fallback
results[].retrieval_rank / retrieval_score
results[].rerank_rank / rerank_score
results[].matched_child_text
results[].returned_parent_text
```

### 多 Collection 统一重排

```json
{
  "query": "隔夜鸡肉还能怎么处理",
  "top_k": 5,
  "mode": "hybrid",
  "collections": ["food_safety", "recipes"]
}
```

系统会在指定 Collection 范围内召回、融合候选，再统一执行一次 Reranker。某个 Collection 失败时，其余候选仍然返回，错误记录在 `errors`。

### Agent JSON

`POST /agent/ask`

```json
{
  "question": "剩菜可以保存多久？",
  "conversation_id": "conv_v3122_food_001",
  "collection": "food_safety",
  "top_k": 5,
  "mode": "hybrid",
  "max_steps": 4,
  "context_max_chunks": 5,
  "context_token_budget": 4000
}
```

### 同一会话追问

```json
{
  "question": "鸡肉的呢？",
  "conversation_id": "conv_v3122_food_001",
  "collection": "food_safety",
  "top_k": 5,
  "mode": "hybrid"
}
```

### 离线对照评估

`POST /rerank/evaluate`

```json
{
  "top_k": 5,
  "mode": "hybrid",
  "cases": [
    {
      "query": "剩菜可以保存多久",
      "relevant_ids": ["KB-FOOD-LEFTOVERS"],
      "collection": "food_safety"
    }
  ]
}
```

`relevant_ids` 可以使用索引中的 `parent_id`、`chunk_id` 或 `source`。评估复用同一召回候选，比较 baseline 与 reranked 的 Hit/Recall@K、MRR、NDCG@K 和 latency。相关文档未进入候选集时会标记 `recall_failed=true`，Reranker 无法修复召回缺失。

## CLI

流式回答：

```bash
.venv/bin/obsidian-rag agent-v3-12-2 ask "剩菜可以保存多久" --collection food_safety
```

同步 JSON：

```bash
.venv/bin/obsidian-rag agent-v3-12-2 ask "剩菜可以保存多久" --collection food_safety --json
```

只观察重排：

```bash
.venv/bin/obsidian-rag agent-v3-12-2 rerank "剩菜可以保存多久" --collection food_safety
```

## 正常链路与条件分支

### 正常链路

1. RetrievalService 将请求的最终 `top_k` 扩大到 `RAG_RERANK_CANDIDATES`。
2. Dense/Keyword 执行 RRF，Parent-Child 结果按 `parent_id` 去重并恢复 Parent。
3. Reranker 使用 `heading_path + matched_child_text` 评分。
4. 结果按 CrossEncoder score 排序并截取 `RAG_RERANK_TOP_K`。
5. ContextBuilder 识别 `rerank_rank`，把 `returned_parent_text` 放入 Context。
6. Answer LLM 生成 JSON 或 `answer_delta` SSE。

### disabled / none

保持 RRF 顺序，`rerank_score=null`，不会导入或加载 `sentence-transformers`。

### empty

没有候选时直接返回空结果，不加载模型。

### timeout / provider error

系统 fail-open，保留 RRF 顺序并设置：

```json
{
  "fallback": true,
  "fallback_reason": "reranker_timeout"
}
```

线程 timeout 是学习版调用边界，无法可靠中断底层 PyTorch 运算；生产环境需要独立模型服务实现硬超时和资源隔离。

### retry

Agent Evidence Checker 触发补搜时，每个 retry query 都重新经过扩大召回和 Reranker。Reranker 回退不会直接触发 Agent retry，因为检索结果仍然可用。

### no_search / clarify

Planner 选择 `no_search` 或 `clarify` 时不会调用检索和 Reranker。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `obsidian_rag/reranking/models.py` | 内部候选、Outcome 和运行摘要 contract。 |
| `obsidian_rag/reranking/providers.py` | Fake 与延迟加载 CrossEncoder Provider。 |
| `obsidian_rag/reranking/service.py` | 排序、timeout、fail-open 和 metadata。 |
| `obsidian_rag/reranking/retrieval.py` | 单库/多库扩大召回、融合和最终截断。 |
| `obsidian_rag/v3_12_2/schemas.py` | Swagger 输入输出及中文字段说明。 |
| `obsidian_rag/v3_12_2/service.py` | 独立 search/evaluate 与 Agent Runtime 编排。 |
| `obsidian_rag/v3_12_2/dependencies.py` | Retrieval、Reranker、Agent 和 SSE 依赖装配。 |
| `obsidian_rag/v3_12_2/routes/` | health、rerank 和 Agent JSON/SSE 路由。 |
| `obsidian_rag/v3_12_2/evaluation.py` | Hit、Recall、MRR、NDCG 指标。 |

## 主流程断点

以下行号按 V3.12.2 完成时代码核对；代码变化后应以函数名重新定位。

| 顺序 | 文件行号 | 函数 | 观察变量 |
| --- | --- | --- | --- |
| 1 | `v3_12_2/service.py:35` | `RerankerLearningService.search` | `request.collection`、`request.collections`、`top_k` |
| 2 | `reranking/retrieval.py:28` | `search_with_outcome` | `candidate_k`、`candidates`、`output_k` |
| 3 | `v1/services/retrieval_service.py:17` | `RetrievalService.search` | `dense_results`、`keyword_results`、`fused` |
| 4 | `parent_retrieval.py:7` | `expand_parent_results` | `parent_id`、`matched_child`、`parent_text` |
| 5 | `reranking/service.py:33` | `RerankingService.rerank` | `scoring_texts`、`scores`、`ranked` |
| 6 | `reranking/service.py:94` | `_fallback` | `reason`、`baseline.summary` |
| 7 | `core/context.py:14` | `ContextBuilder.build` | `candidates`、`ranked`、`included` |
| 8 | `core/agent/service.py:570` | `_synthesize_answer_node` | `context_bundle.messages`、answer stream |

多 Collection 额外断点：

| 顺序 | 文件行号 | 函数 | 观察变量 |
| --- | --- | --- | --- |
| 1 | `reranking/retrieval.py:53` | `search_collections` | `results_by_collection`、`errors` |
| 2 | `reranking/retrieval.py:92` | `_cross_collection_candidates` | `collection_rank`、`cross_collection_score` |

流程图：[rag-v3-12-2-reranking-flow.svg](assets/rag-v3-12-2-reranking-flow.svg)
