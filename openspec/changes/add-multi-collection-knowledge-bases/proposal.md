## Why

当前所有 ingest、dense retrieval 和 hybrid retrieval 都共享 `obsidian_notes`。食品安全、菜谱等不相关知识混入同一检索空间会降低召回质量，也使一次 `recreate` 难以限定影响范围。

## What Changes

- 为共享 V0 pipeline 增加请求级 `collection` 选择；未提供时继续使用 `RAG_COLLECTION` 默认值。
- 将 Qdrant collection 与 KeywordIndex 一一绑定，避免多 collection 时 hybrid retrieval 的 dense 与 keyword 结果混用。
- 在 V0 API / CLI、V3.11.1 Docling API / CLI 和共享 Agent 检索入口传播 collection 选择，并在响应中回显实际 collection。
- 对 collection 名称进行统一校验；`recreate` 仅重建当前指定 collection 及其 keyword index。
- 补充 Swagger、CLI、学习文档和测试，说明重新 ingest 的迁移方式。

## Capabilities

### New Capabilities

- `collection-scoped-knowledge-bases`: 在单个 RAG 实例中创建、写入和检索相互隔离的知识库 collection，并让 dense / keyword / hybrid 结果保持同一范围。

### Modified Capabilities

- 无；仓库尚未建立对应的基线 OpenSpec capability。

## Impact

- 受影响代码：`config.py`、`pipeline.py`、`v1/retrieval/keyword.py`、`v1` API/CLI、`v3_11_1` 和 Agent 检索入口。
- 现有不传 `collection` 的调用继续使用 `RAG_COLLECTION`，保持默认行为。
- 旧的单一 `keyword_index.json` 不再作为多 collection 的共享索引；每个 collection 需要重新 ingest。
- 不增加依赖，不实现自动分类、跨 collection 聚合检索或知识库权限管理。
