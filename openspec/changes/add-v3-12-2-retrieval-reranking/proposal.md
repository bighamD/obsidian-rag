## Why

当前主线在 Dense 与 Keyword 召回后只执行 RRF、Parent Expansion 和按分数截断，无法进一步判断 `query + chunk` 的真实相关性；多 Collection 和相似候选增多后，RRF 排名错误会直接进入 LLM Context。V3.12.2 应在进入 V3.13 Permission Policy 前插入独立的 Retrieval Reranking 学习版本，用可量化对照理解召回、融合、重排和 Context 选择的职责边界。

## What Changes

- 新增独立 `obsidian_rag/v3_12_2/` 学习版本，把共享检索候选送入可插拔 Reranker，再交给 ContextBuilder 和 Answer LLM。
- 在公共检索层增加稳定的 Reranker contract，提供 `none` 基线和本地 `sentence-transformers CrossEncoder` 实现；模型通过配置选择，推荐中文/多语言知识库使用 BGE Reranker。
- 保留候选的 Dense、Keyword、RRF 与 Rerank 分数和排名，记录输入/输出数量、耗时、provider/model 与 fallback 原因。
- 支持超时、依赖缺失、模型加载或推理失败时安全回退到 RRF 顺序，不阻断回答主链路。
- 增加离线对照评估与固定测试案例，比较 RRF only 和 RRF + Reranker 的 MRR/NDCG、最终 Context 命中情况及延迟。
- 提供独立 FastAPI JSON/SSE、Swagger 示例、CLI、测试、学习文档、SVG、文件职责和按当前行号核对的断点指南。
- 更新学习路线，说明 V3.12.2 是 Retrieval Quality 插入版本，完成后回到 V3.13 Permission Policy 主线。

## Capabilities

### New Capabilities

- `retrieval-reranking-runtime`: 定义候选重排 contract、本地 CrossEncoder Adapter、配置、失败回退、可观测结果，以及 V3.12.2 API/CLI 学习闭环。
- `reranking-evaluation`: 用固定查询与相关性标注对比 RRF 基线和 Reranker 的排序质量、Context 选择及延迟。

### Modified Capabilities

<!-- 当前 openspec/specs/ 没有需要修改的既有正式 capability。 -->

## Impact

- 代码：新增公共 reranking 模块、`obsidian_rag/v3_12_2/`、CLI/launch 配置、测试和学习资料；在 V3.12.2 入口接入现有 RetrievalService、Parent Expansion、ContextBuilder 与 Streaming Runtime。
- 配置：新增 Reranker enabled/provider/model、候选数、Top K、timeout、device 和 fallback 配置；默认保持可关闭和可回退。
- 依赖：`sentence-transformers`/PyTorch 作为可选 rerank extra，避免所有基础安装被本地模型依赖拖重；单元测试使用 fake reranker，不下载模型。
- 数据：不改变现有 Qdrant Collection、keyword index、chunk schema 或 Memory 数据，无需重新 ingest。
- API：V3.12.2 增加重排详情和运行配置字段；V3.12.1 对外契约保持不变。
