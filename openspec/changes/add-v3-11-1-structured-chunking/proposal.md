## Why

当前共享 V0 ingest 需要同时解决多格式解析和生产 chunk 完整性。Docling `HybridChunker` 能提供可靠原子 blocks，但直接一对一入库会把同一父章节拆得过碎，因此 V3.11.1 在 Docling Parser 后增加通用 adaptive parent-child 策略。

## What Changes

- 在共享 V0 ingest 中增加 Docling backend，支持 Docling 当前可转换的 PDF、Markdown、DOCX、PPTX、XLSX、HTML、CSV 和图片等格式。
- 使用 `DocumentConverter` 生成 `DoclingDocument`，保留标题、页码、表格、图片与来源等结构 metadata。
- 使用 Docling `HybridChunker` 产生结构 blocks，再按 `heading_path` 合并同父小块；超长 parent 复用 LangChain recursive splitter。
- 默认索引 child，并在 dense/keyword/hybrid 检索后按 `parent_id` 返回完整 parent。
- 将 Docling chunks 映射为现有 `TextChunk`，继续复用 embedding、Qdrant、keyword index、V1～V3.11 检索与 V2 evaluation。
- 新增独立 `obsidian_rag/v3_11_1/`，提供 convert/chunk preview、ingest、search 的 FastAPI JSON/Swagger、CLI 与调试 trace。
- **BREAKING**：默认写入 `parent-child-v1` schema，需要通过 `recreate` 重建当前 collection 和 keyword index。

## Capabilities

### New Capabilities

- `docling-document-ingestion`: 使用 Docling 完成多格式转换、结构化预览、HybridChunker 切片和共享 V0 入库。

### Modified Capabilities

无。

## Impact

- 新增 Docling 依赖及其文档模型、OCR/布局处理能力。
- 修改共享 V0 pipeline 的 ingest 与 retrieval；保留 `docling_hybrid` chunk strategy 作为学习基线。
- 新增 `obsidian_rag/v3_11_1/`、CLI、Swagger、测试、文档和 SVG。
- V3.11.2 继续保留三框架实验；其中 LangChain Parent 模式已经迁移为共享生产策略。
- V3.12 MCP Integration 主线不变。
