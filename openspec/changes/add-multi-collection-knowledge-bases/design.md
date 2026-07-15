## Context

`RagConfig.collection_name` 已经会传给 Qdrant，因此向量层可以拥有多个 collection；但它只能在进程启动时通过 `RAG_COLLECTION` 设定。与此同时，keyword retrieval 始终读写 `.rag/keyword_index.json`，所以仅切换 Qdrant collection 会让 hybrid retrieval 混用不同知识库的数据。

V0 pipeline 是 V3.11.1、V1 retrieval 和 V3.8.1/3.11 Agent 的共同检索基础。collection 选择必须成为请求范围内的配置，不能修改共享的全局 config，否则 FastAPI 并发请求会相互污染。

## Goals / Non-Goals

**Goals:**

- 让单个实例可安全维护 `food_safety`、`recipes` 等相互独立的 collection。
- 对每个 collection 使用独立的 Qdrant 与 keyword index 数据面。
- 让 API、CLI、Docling 和 Agent 的同一次请求始终在同一个 collection 中 ingest 或检索。
- 保持未传 collection 的现有调用使用 `RAG_COLLECTION` 默认值。

**Non-Goals:**

- 不根据文档内容自动选择 collection。
- 不实现跨 collection 并行检索和 RRF 融合。
- 不实现知识库注册表、权限、租户隔离、删除 collection 或后台迁移。
- 不改变 embedding 模型；所有 collection 在当前实例中继续使用同一 embedding 配置。

## Decisions

### 1. 使用请求级 `collection`，不是全局环境切换

`collection` 是可选 API JSON 字段和 CLI `--collection` 选项。未传时使用 `RagConfig.collection_name`；传入后通过不可变 config copy 覆盖 `collection_name`，传递给 Qdrant、dense retrieval 和 keyword retrieval。

选择请求级覆盖而非每个 collection 启动一个服务，是为了让同一 API 进程能服务多个知识库，并避免共享环境变量的并发竞态。

### 2. collection 名称是受限的存储命名空间

collection 名称必须匹配小写 `[a-z0-9][a-z0-9_-]{0,62}`。这是用户可读、可预测的物理命名空间，例如 `food_safety`、`recipes`；`category`、`tags` 仍是 collection 内的 metadata 过滤维度，不能替代 collection。

### 3. KeywordIndex 按 collection 隔离

keyword index 位置改为 `.rag/keyword_indexes/<collection>.json`。pipeline 写入和 `RetrievalService` 读取必须使用同一 collection-derived path，保证 hybrid RRF 的两条召回链路一致。`recreate=true` 只会重建当前 Qdrant collection，并以当前 ingest chunks 覆盖该 collection 的 keyword index。

`recreate=false` 时，pipeline 会加载当前 collection 已有的 keyword index，再按与 Qdrant point 相同的稳定标识合并本批 chunks。这样增量 ingest 后，dense 与 keyword 两条召回链路仍包含同一批数据。每次共享 pipeline 操作结束都会关闭 embedded Qdrant client，避免连续写入不同 collection 时遗留文件锁。

选择独立文件而非在单一 JSON 内加 collection 字段，能够避免整库加载、误写和跨 collection 查询，也使本地调试更直观。

### 4. 贯通公共服务面，而不是只修改 ingest

V0 `ingest/search/compare-search/ask`、V3.11.1 `documents ingest/search`、相应 CLI 命令都会接受 collection 并在 response 回显。V3.8.1 Agent 和 V3.11 Skill Agent 将 collection 固化到一次 ask 创建的 search tool closure 中，使 planner 重试搜索也不越界。

`convert/chunks` 是只读解析预览，不访问 Qdrant / keyword index，因此不增加 collection 参数。

## Risks / Trade-offs

- [旧 keyword index 无法自动分库] → 首次使用新 collection 路径后，对每个知识库执行一次显式 ingest；旧文件保留但不再被读取。
- [请求未传 collection] → 回退 `RAG_COLLECTION`，保持现有脚本可用；response 回显实际 collection 便于排查。
- [非法 collection 名称] → API 在 schema 层拒绝，CLI / service 在统一 resolver 处给出可读错误。
- [后续不同 collection 采用不同 embedding 模型] → 当前不支持；未来知识库注册表需要记录 model 与 dimension，且跨库检索需要额外策略。
