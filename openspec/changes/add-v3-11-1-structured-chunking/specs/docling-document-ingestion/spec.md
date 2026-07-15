## ADDED Requirements

### Requirement: Docling multi-format conversion
系统 SHALL 使用 Docling `DocumentConverter` 转换受支持的本地文档，并返回 `DoclingDocument` 的格式、标题、页数、结构项数量和 Markdown 预览。

#### Scenario: Convert one document
- **WHEN** 用户提交一个 Docling 支持的本地文件路径
- **THEN** 系统返回转换摘要与 Markdown 预览，并保留源路径和转换状态

#### Scenario: Framework dependency missing
- **WHEN** Docling 依赖未安装且用户调用 Docling 接口
- **THEN** 系统返回明确错误，说明应安装的项目依赖，不影响其它版本导入

### Requirement: Adaptive parent-child chunking
系统 SHALL 使用 Docling `HybridChunker` 产生结构 blocks，默认合并同父小块，并只在 parent/child 超过 token 阈值时递归切分。

#### Scenario: Chunk a structured document
- **WHEN** DoclingDocument 包含标题、段落或表格
- **THEN** 每个 child 保留 `parent_id`、`parent_text`、heading path、页码和业务 metadata

#### Scenario: Merge small sibling blocks
- **WHEN** 多个短 blocks 属于同一个结构 parent 且合并后未超过阈值
- **THEN** 系统生成一个完整 parent，并直接使用该 parent 作为单个检索 child

#### Scenario: Split an oversized parent
- **WHEN** 完整结构 parent 超过 child 或 parent token 阈值
- **THEN** 系统按标题、段落、句子和 token 递归生成多个 child，并共享 parent ID

### Requirement: Shared V0 ingestion backend
共享 V0 pipeline SHALL 固定使用 Docling Parser，并支持 `adaptive_parent_child` 与 `docling_hybrid` 两种 chunk strategy；默认使用前者。

#### Scenario: Recreate Docling index
- **WHEN** backend 为 docling 且 ingest 使用 `recreate=true`
- **THEN** 系统使用 `parent-child-v1` children 重建当前 collection 并覆盖 keyword index

#### Scenario: Child retrieval and parent return
- **WHEN** dense、keyword 或 hybrid 命中一个或多个 children
- **THEN** 系统保留 matched child 证据，按 parent ID 去重并返回完整 parent text

### Requirement: V3.11.1 learning surface
系统 SHALL 提供独立 FastAPI JSON/Swagger、CLI、测试、trace 和文档，解释 Docling Converter、DoclingDocument、HybridChunker、contextualized text 与 Qdrant payload 的职责。

#### Scenario: Inspect chunks without indexing
- **WHEN** 用户调用 chunks preview API 或 CLI
- **THEN** 系统展示 Docling chunk 及其 metadata，但不写入 Qdrant
