## Why

当前共享 V0 ingest 将 Markdown/PDF 扁平化后按字符窗口切片，无法学习多格式布局解析、表格/OCR 和统一文档模型。V3.11.1 改用 Docling 的 `DocumentConverter`、`DoclingDocument` 与 `HybridChunker`，把学习重点放在主流 Document AI 框架的能力边界和工程接入，而不是自研解析算法。

## What Changes

- 在共享 V0 ingest 中增加 Docling backend，支持 Docling 当前可转换的 PDF、Markdown、DOCX、PPTX、XLSX、HTML、CSV 和图片等格式。
- 使用 `DocumentConverter` 生成 `DoclingDocument`，保留标题、页码、表格、图片与来源等结构 metadata。
- 使用 Docling `HybridChunker` 完成结构优先、token-aware 的切片与 contextualize，不自行实现递归切片算法。
- 将 Docling chunks 映射为现有 `TextChunk`，继续复用 embedding、Qdrant、keyword index、V1～V3.11 检索与 V2 evaluation。
- 新增独立 `obsidian_rag/v3_11_1/`，提供 convert/chunk preview、ingest、search 的 FastAPI JSON/Swagger、CLI 与调试 trace。
- **BREAKING**：V3.11.1 写入 `docling-v1` chunk schema，需要通过 `recreate` 重建当前 collection 和 keyword index。

## Capabilities

### New Capabilities

- `docling-document-ingestion`: 使用 Docling 完成多格式转换、结构化预览、HybridChunker 切片和共享 V0 入库。

### Modified Capabilities

无。

## Impact

- 新增 Docling 依赖及其文档模型、OCR/布局处理能力。
- 修改共享 V0 pipeline 的 ingest 入口，但保留现有 legacy loader/chunker 作为显式 fallback。
- 新增 `obsidian_rag/v3_11_1/`、CLI、Swagger、测试、文档和 SVG。
- V3.11.2 将在同一语料上继续引入 LangChain/LlamaIndex，不在本版本混入父子或语义检索框架。
- V3.12 MCP Integration 主线不变。
