# V3.11.1 Docling Structured Ingestion 学习指南

V3.11.1 在 V3.11 Skill System 与 V3.12 MCP Integration 之间补充多格式文档数据基础。它不修改 Agent 行为，而是把共享 V0 ingest 从“Markdown/PDF 纯文本 loader + 字符切片”升级为可选择的 Docling framework backend。

![V3.11.1 Docling Structured Ingestion](assets/rag-v3-11-1-docling-flow.svg)

## 当前版本做什么

```text
PDF / Markdown / DOCX / PPTX / XLSX / HTML / CSV / Image
                              │
                              ▼
                   Docling DocumentConverter
                              │
                              ▼
                       DoclingDocument
                              │
                              ▼
          HybridChunker + HuggingFaceTokenizer
                              │
                              ▼
                     TextChunk adapter
                              │
                              ▼
          Embedding -> Qdrant + KeywordIndex
```

- 使用 Docling `DocumentConverter` 处理框架支持的本地格式。
- 用 `DoclingDocument.export_to_markdown()` 展示统一文档结果。
- 使用官方 `HybridChunker`，不自研递归切片算法。
- 同时保留 `chunk.text` 与 `HybridChunker.contextualize()`。
- 将 headings、captions、origin、doc_items provenance 和页码映射到 metadata。
- 通过共享 V0 pipeline 写入现有 Qdrant 与 keyword index。
- 提供 convert、chunks、ingest、search 四个 JSON 接口和对应 CLI。

## 当前版本不做什么

- 不实现 LangChain ParentDocumentRetriever。
- 不实现 LlamaIndex AutoMergingRetriever 或 SemanticSplitter。
- 不重新实现 PDF Layout、OCR、表格识别或 Markdown AST。
- 不改写 V3.11 Skill Registry、Router 或 Agent。
- 不提供 SSE、后台任务、转换缓存或旧索引迁移。

这些框架检索能力由 V3.11.2 继续学习；V3.12 仍回到 MCP Integration 主线。

## 相比旧 V0 改进了什么

| 维度 | legacy backend | docling backend |
| --- | --- | --- |
| 格式 | Markdown、PDF | Docling 当前支持的多格式 |
| 文档模型 | 扁平 `SourceDocument.text` | `DoclingDocument` |
| PDF | `pypdf.extract_text()` | Docling layout/OCR pipeline |
| Chunk | 自定义字符窗口 | Docling `HybridChunker` |
| 长度 | 字符数 | tokenizer token 上限 |
| 表格 | 普通文本 | Docling table item + provenance |
| Embedding 文本 | chunk 原文 | `contextualize(chunk)` |

## 配置

```dotenv
RAG_DOCUMENT_PARSER=docling
RAG_DOCLING_TOKENIZER_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_CHUNK_TOKENS=512
```

首次使用 Docling 可能下载布局、OCR 或 tokenizer 模型。若需要回到原来的 loader/chunker：

```dotenv
RAG_DOCUMENT_PARSER=legacy
```

`legacy` 是显式学习/故障回退，不是 V3.11.1 主路径。

## Swagger JSON 示例

API 入口：

```bash
.venv/bin/uvicorn obsidian_rag.v3_11_1.app:app --host 127.0.0.1 --port 8016
```

### 1. Convert 单文件

`POST /documents/convert`

```json
{
  "path": "knowledge/manual.pdf"
}
```

返回 `DoclingDocument` 的标题、状态、页数、结构项数量和 Markdown 预览，不执行 chunk 或入库。

### 2. Preview HybridChunker

`POST /documents/chunks`

```json
{
  "path": "knowledge/manual.pdf"
}
```

关键响应字段：

| 字段 | 含义 |
| --- | --- |
| `raw_text` | Docling `chunk.text` 原始内容 |
| `contextualized_text` | 实际用于 embedding 的 headings/captions + text |
| `metadata.docling` | Docling chunk meta 的 JSON 投影，仅用于调试和定位 |
| `heading_path` | 标题路径 |
| `page_numbers` | provenance 中提取的页码 |
| `node_id` | 映射到 Qdrant point 的稳定 ID |

### 3. 重建索引

`POST /documents/ingest`

```json
{
  "path": "knowledge",
  "recreate": true
}
```

本版本 chunk schema 为 `docling-v1`，首次 ingest 应使用 `recreate=true`。它会覆盖当前 Qdrant collection 和 keyword index；不会删除源文件。

### 4. 检索 Docling chunks

`POST /documents/search`

```json
{
  "query": "这个文档的核心结论是什么？",
  "top_k": 5,
  "mode": "hybrid"
}
```

## CLI

```bash
.venv/bin/obsidian-rag documents-v3-11-1 convert knowledge/manual.pdf
.venv/bin/obsidian-rag documents-v3-11-1 chunks knowledge/manual.pdf
.venv/bin/obsidian-rag documents-v3-11-1 ingest knowledge --recreate
.venv/bin/obsidian-rag documents-v3-11-1 search "核心结论是什么？" --top-k 5 --mode hybrid
```

## 正常主链路

```text
CLI / Swagger
  -> DoclingLearningService
  -> DoclingIngestion
  -> DocumentConverter.convert
  -> DoclingDocument
  -> HybridChunker.chunk
  -> HybridChunker.contextualize
  -> TextChunk(metadata.docling)
  -> embedding
  -> Qdrant + KeywordIndex
```

## 条件分支

| 分支 | 行为 |
| --- | --- |
| `RAG_DOCUMENT_PARSER=docling` | 使用 Converter + HybridChunker 主链路 |
| `RAG_DOCUMENT_PARSER=legacy` | 继续使用原 loader/chunker |
| Docling 依赖缺失 | 返回明确的 `pip install -e .` 提示 |
| 单文件 convert 传入目录 | 返回参数错误，提示改用 chunks/ingest |
| 目录中个别文件转换失败 | chunks preview 返回 `errors`，成功文件继续展示 |
| 所有文件转换失败 | ingest 中止，不写入空索引 |
| tokenizer/model 首次使用 | 可能下载模型，耗时高于后续运行 |

## 文件职责

| 文件 | 作用 |
| --- | --- |
| `obsidian_rag/docling_ingestion.py` | Docling Converter/HybridChunker 薄适配和 TextChunk metadata 映射 |
| `obsidian_rag/pipeline.py` | 根据 `RAG_DOCUMENT_PARSER` 选择 docling 或 legacy，然后统一 embed/upsert |
| `obsidian_rag/config.py` | parser、tokenizer 和 token 上限配置 |
| `obsidian_rag/v3_11_1/schemas.py` | Swagger 输入输出职责与字段中文说明 |
| `obsidian_rag/v3_11_1/service.py` | convert/chunks/ingest/search 学习编排 |
| `obsidian_rag/v3_11_1/routes/` | FastAPI JSON 路由 |
| `obsidian_rag/v3_11_1/app.py` | V3.11.1 FastAPI app |
| `tests/v3_11_1/` | Docling adapter、service、API、CLI 测试 |

## 核心断点顺序

| 顺序 | 文件行号与函数 | 观察变量 |
| --- | --- | --- |
| 1 | `v3_11_1/service.py:41` `DoclingLearningService.convert()` | `path`、`request.path` |
| 2 | `docling_ingestion.py:74` `DoclingIngestion.convert_file()` | `result.status`、`document`、`markdown` |
| 3 | `v3_11_1/service.py:49` `DoclingLearningService.chunks()` | `batch.conversions`、`batch.errors` |
| 4 | `docling_ingestion.py:90` `chunk_conversion()` | `chunk.text`、`contextualized`、`docling_meta` |
| 5 | `docling_ingestion.py:124` `convert_and_chunk_path()` | `files`、`conversions`、`chunks`、`errors` |
| 6 | `pipeline.py:56` `ingest_path()` | `config.document_parser`、`document_count`、`chunks` |
| 7 | `pipeline.py:17` `make_embedding_client()` | embedding provider/model |
| 8 | `qdrant_store.py:48` `upsert()` | point payload、`node_id`、vector dimensions |

行号已经按版本完成时的代码核对。后续代码变化后，应优先按函数名重新定位。

## 测试与边界

- adapter 测试使用 Docling fake，验证 headings、KB ID、provenance page 和 schema 映射。
- service/API/CLI 测试不下载真实模型，也不连接 Qdrant。
- 真正的布局/OCR 效果必须用本地代表性 PDF/图片执行 chunks preview 后再评估。
- 本版本不会自动启动 API；由用户自行运行 Swagger 和断点调试。

## 下一版本

V3.11.2 使用同一个 Docling Markdown 输入对比：

```text
LangChain RecursiveCharacterTextSplitter + ParentDocumentRetriever
LlamaIndex HierarchicalNodeParser + AutoMergingRetriever
LlamaIndex SemanticSplitterNodeParser
```
