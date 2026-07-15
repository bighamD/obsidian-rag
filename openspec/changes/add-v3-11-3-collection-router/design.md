## Context

共享 V0/V1 pipeline 已支持请求级 collection，且当前数据分别位于 `food_safety`、`recipes`、`vueuse_core_kb`。V3.11 Agent 和 CLI 只能接收一个显式 collection；调用方不指定时回退 `RAG_COLLECTION`。本地 keyword index 也按 collection 隔离，因此多库检索必须先确定有限范围，再分别调用现有 RetrievalService，不能加载全部索引后无边界扫描。

V3.11.3 是 V3.12 MCP 前的专项学习版本。它位于查询决策层，不能修改 V3.11.1 的 Docling parser/chunker 责任，也不应把 Collection Router 混同于 V3.11 Skill Router：前者决定“查哪些语料库”，后者决定“采用什么任务方法”。

## Goals / Non-Goals

**Goals:**

- 让 Agent Console 能显式传递 collection。
- 用可审查的 YAML Registry 描述可路由知识库。
- 实现显式优先、LLM 自动选择零至两个 collection 的结构化路由。
- 复用现有 dense/keyword/hybrid retrieval，并在多库结果之上执行跨库 RRF。
- 提供 JSON API、CLI、trace、测试、断点文档和 SVG 学习闭环。

**Non-Goals:**

- 不把 Router 接入 V3.11 完整 Agent、Memory、Skill Runtime 或 SSE。
- 不实现 ACL、租户隔离、自动建库、跨库写入或 collection 删除。
- 不把本地 keyword index 替换为 Qdrant sparse vector，也不增加 reranker。
- 不默认扫描 Registry 中的全部 collection。

## Decisions

### 1. Registry 使用 YAML 文件和严格模型

新增根目录 `knowledge_bases.yaml`，默认由 `RAG_KNOWLEDGE_BASE_REGISTRY` 覆盖路径。每项包含 `id`、`collection`、`description`、`triggers`、`enabled`。Registry 只提供路由元数据，不保存凭据或文档正文；collection 继续复用共享配置层的名称校验。

选择 YAML 而不是数据库，是为了让本学习版本可读、可调试且不增加依赖；后续需要动态管理、权限和版本状态时再迁移到持久化 Registry。

### 2. 路由优先级固定为显式选择优先

执行顺序为：

1. 请求提供 `collection`：校验其存在且启用，状态为 `explicit`，不调用 LLM。
2. 请求关闭 Router：使用 `RAG_COLLECTION`，状态为 `disabled`；默认库未登记时返回 `invalid_selection`。
3. 其他请求：LLM 只能从启用的 Registry candidates 中选择零至 `max_collections` 个。

Router 返回 `selected`、`multi_selected`、`no_collection`、`explicit`、`disabled`、`invalid_selection` 或 `router_error`，并保留简短可观察原因和置信度，不返回 chain-of-thought。

### 3. 最多并行查询两个 collection

`max_collections` 默认 2 且上限 3。多库检索使用标准库 `ThreadPoolExecutor` 并行调用现有 `RetrievalService.search()`；单库请求直接调用，避免线程开销。每个命中 metadata 增加实际 `collection`，但不修改 Qdrant 原 payload。

选择有限 fan-out 而不是遍历所有 Registry，是为了控制 embedding、Qdrant 和 keyword JSON 加载成本，也让 Router 决策可评估。

### 4. 跨库融合只使用排名

每个 collection 先完成自己的 dense/keyword/hybrid 策略，再以 collection 内排名执行第二层 RRF。跨库 key 必须包含 collection，避免不同知识库复用相同 `chunk_id` 时被错误去重。响应保留 `collection_rank`、`cross_collection_score` 和各库命中数。

不同 collection 的原始 dense/BM25 分数不可直接比较，因此本版本不做原始 score 归一化或加权；reranker 留待后续版本。

### 5. V3.11.3 保持 JSON-first 的查询学习边界

提供：

- `GET /collections`
- `POST /collections/route`
- `POST /collections/search`
- CLI `collections-v3-11-3 list|route|search`

本版本返回检索结果，不调用 Answer LLM，也不新增 SSE。未来 Agent 集成可以把同一个 scoped retrieval adapter 注入 V3.11，而不修改本版本的 Registry/Router contract。

## Risks / Trade-offs

- [LLM Router 增加延迟和费用] → 显式 collection 永远优先；Router 只接收轻量 Registry metadata。
- [Router 选择错误知识库] → 返回 candidate、selection、confidence 和 trace，支持独立评测；限制最多两个库。
- [本地 keyword JSON 每次加载] → 保持当前学习版实现；生产化后迁移 Qdrant sparse 或搜索引擎。
- [多库 RRF 丢失原始分数量纲] → 响应保留单库 score 和跨库 score；未来通过 reranker 改进。
- [Registry 与实际 Qdrant 状态不一致] → Registry 只声明可查询范围，search 错误按 collection 记录并让其他库继续返回。

## Migration Plan

1. 增加 Registry 文件并登记三个现有 collection，无需重新 ingest。
2. 前端发布 collection 参数后仍兼容 V3.11 API。
3. V3.11.3 使用独立 app、端口和 CLI，不替换现有 V3.11/V3.11.1 服务。
4. 若需回滚，只停止 V3.11.3 服务；现有 collection、keyword index 和 V3.11 Agent 不受影响。

## Open Questions

- 后续是否将 Router 选择结果固化到 conversation scope，需要在接入 Agent Memory 时单独设计。
- Qdrant sparse vector 与 reranker 的生产化演进不在本版本决定。
