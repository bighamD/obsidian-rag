## Context

V0 `ingest_path()` 是所有后续版本共用的数据入口。仓库已有 `SourceDocument`、`TextChunk`、embedding、Qdrant、BM25 与 V2 evaluation，但没有布局解析框架。用户更关注主流技术方向，因此 V3.11.1 应展示 Docling 的标准模型与 chunker，而不是维护一套自研 AST、tokenizer 或递归算法。

## Goals / Non-Goals

**Goals:**

- 使用 Docling `DocumentConverter` 处理本地多格式文件。
- 在 preview 中直接展示 `DoclingDocument` 摘要、原始 chunk metadata 和 contextualized text。
- 使用 `HybridChunker` 作为唯一主切片实现，并映射到仓库 `TextChunk`。
- 让共享 V0 ingest 可选择 `docling` 或 `legacy` backend，默认使用 Docling。
- 复用现有向量库、关键词索引、检索和评估链路。

**Non-Goals:**

- 不自研 Markdown/PDF Parser、Document Tree、递归切片或 OCR。
- 不在本版本实现 LangChain ParentDocumentRetriever、LlamaIndex AutoMerging 或语义切片。
- 不提供旧索引迁移或双写。
- 不新增 SSE，不修改 V3.11 Skill System。

## Decisions

### 1. Docling 作为框架依赖，采用延迟构造

共享模块 `docling_ingestion.py` 在实际 convert/chunk 时导入 `DocumentConverter`、`HybridChunker` 与 `HuggingFaceTokenizer`。依赖缺失时抛出包含安装命令的明确错误，现有 search/agent 导入不受影响。

### 2. V0 pipeline 通过 backend 选择，不复制 ingest

`RAG_DOCUMENT_PARSER=docling|legacy` 控制 `ingest_path()`：Docling backend 直接从文件路径产生 `TextChunk`；legacy backend 保留原 loader/chunker，便于学习对照和故障回退。V3.11.1 API 固定展示 Docling 路径。

### 3. 使用 Docling 官方 HybridChunker

使用 `HuggingFaceTokenizer.from_pretrained(model_name, max_tokens)` 配置 token 上限，再传给 `HybridChunker`。embedding 文本使用 `chunker.contextualize(chunk)`；`chunk.text`、headings、captions、origin、doc_items provenance 作为调试 metadata 保留。

### 4. 只做薄适配

每个 Docling chunk 映射为：

- `TextChunk.text`：contextualized text，直接用于 embedding/keyword search。
- `metadata.source`：相对源路径。
- `metadata.node_id`：source + chunk index 的稳定 UUID。
- `metadata.docling`：Docling chunk meta 的 JSON 投影。
- `metadata.heading_path/page_numbers`：从 Docling meta 提取的常用定位字段。
- `metadata.chunk_schema_version=docling-v1`。

不额外复制 Docling 内部树模型。

### 5. V3.11.1 学习接口

- `POST /documents/convert`：转换一个文件，返回 DoclingDocument 摘要和 Markdown 预览。
- `POST /documents/chunks`：执行 HybridChunker，返回原始 text、contextualized text 和 metadata。
- `POST /documents/ingest`：调用共享 V0 Docling ingest。
- `POST /documents/search`：复用现有 RetrievalService。
- CLI：`documents-v3-11-1 convert|chunks|ingest|search`。

## Risks / Trade-offs

- [Docling 安装和模型体积较大] → 文档明确首次运行会下载模型；延迟构造避免无关命令启动成本。
- [HybridChunker tokenizer 与实际 embedding tokenizer 不完全一致] → tokenizer/model/max_tokens 显式展示，V2 evaluation 负责验证效果。
- [不同格式的 Docling metadata 不完全一致] → 保存原始 JSON，并只提取稳定公共字段。
- [OCR/布局转换耗时] → preview 支持文件级输入；目录 ingest 按文件顺序处理并记录失败路径。

## Migration Plan

1. 安装框架依赖并使用 convert/chunks preview 验证代表性文件。
2. 设置 `RAG_DOCUMENT_PARSER=docling`。
3. 使用 `recreate=true` 重建 Qdrant 和 keyword index。
4. 运行 V2 retrieval evaluation；需要回退时改回 `legacy` 并重新 ingest。

## Open Questions

- 大规模 OCR 的并发、缓存与 GPU 优化不在本版解决。
