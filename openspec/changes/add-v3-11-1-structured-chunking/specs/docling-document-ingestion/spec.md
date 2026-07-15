## ADDED Requirements

### Requirement: Docling multi-format conversion
系统 SHALL 使用 Docling `DocumentConverter` 转换受支持的本地文档，并返回 `DoclingDocument` 的格式、标题、页数、结构项数量和 Markdown 预览。

#### Scenario: Convert one document
- **WHEN** 用户提交一个 Docling 支持的本地文件路径
- **THEN** 系统返回转换摘要与 Markdown 预览，并保留源路径和转换状态

#### Scenario: Framework dependency missing
- **WHEN** Docling 依赖未安装且用户调用 Docling 接口
- **THEN** 系统返回明确错误，说明应安装的项目依赖，不影响其它版本导入

### Requirement: Official HybridChunker
系统 SHALL 使用 Docling `HybridChunker` 与显式 tokenizer/max_tokens 生成 chunks，并同时返回原始 chunk text 与 `contextualize()` 后的 embedding text。

#### Scenario: Chunk a structured document
- **WHEN** DoclingDocument 包含标题、段落或表格
- **THEN** 每个结果保留 headings、captions、origin、doc_items provenance 和 contextualized text

### Requirement: Shared V0 ingestion backend
共享 V0 pipeline SHALL 支持 `docling` 和 `legacy` 两种 parser backend，默认使用 Docling，并继续写入现有 Qdrant 与 keyword index。

#### Scenario: Recreate Docling index
- **WHEN** backend 为 docling 且 ingest 使用 `recreate=true`
- **THEN** 系统使用 `docling-v1` chunks 重建当前 collection 并覆盖 keyword index

#### Scenario: Explicit legacy fallback
- **WHEN** backend 明确设置为 legacy
- **THEN** 系统继续使用原有 loader/chunker，不调用 Docling

### Requirement: V3.11.1 learning surface
系统 SHALL 提供独立 FastAPI JSON/Swagger、CLI、测试、trace 和文档，解释 Docling Converter、DoclingDocument、HybridChunker、contextualized text 与 Qdrant payload 的职责。

#### Scenario: Inspect chunks without indexing
- **WHEN** 用户调用 chunks preview API 或 CLI
- **THEN** 系统展示 Docling chunk 及其 metadata，但不写入 Qdrant
