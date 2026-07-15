## Why

当前知识库把业务引用 ID 写在每个二级标题块的 YAML 元数据中，例如 `chunk_id: VU-001`。V0 和 V3.11.1 却把 `KB-...` 当作唯一合法 ID 和分段线索，导致非食品安全知识库丢失 chunk 元数据，并在后续 Context Builder、引用展示和评测中被降级处理。

## What Changes

- 将 `chunk_id` 定义为文档作者提供的可选业务标识，而不是 `KB-` 前缀专属字段。
- 从 Markdown 标题块内的 fenced YAML 提取 `chunk_id`、`title`、`category`、`tags` 和 `source`，并映射到 chunk metadata。
- 让 legacy Markdown chunker 按带结构化 `chunk_id` 的二级标题块建立语义边界；保留没有 YAML 时的通用标题编号兼容兜底。
- 让 V3.11.1 Docling adapter 将同一标题块的结构化 metadata 绑定到 HybridChunker 产出的 chunks；继续保留系统生成的 `node_id`。
- 更新 Swagger 字段描述、学习文档和测试，明确 `KB-072`、`VU-001` 等均为兼容的业务 ID。

## Capabilities

### New Capabilities

- `structured-chunk-metadata`: 从 Markdown 结构化元数据泛化提取和传播业务 chunk 元数据，兼容任意 ID 前缀。

### Modified Capabilities

- 无；仓库尚未建立对应的基线 OpenSpec capability。

## Impact

- 受影响代码：`obsidian_rag/docling_ingestion.py`、`obsidian_rag/v3_11_1/schemas.py`。
- 受影响下游：Context Builder、引用标签、检索评测将能继续使用非 `KB-` 的 `chunk_id`。
- 不新增第三方依赖；复用现有 `PyYAML`。
- 本地 `knowledge/` 目录仅用于手工验证，不纳入版本控制。
