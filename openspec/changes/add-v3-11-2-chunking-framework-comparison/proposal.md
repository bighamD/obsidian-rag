## Why

V3.11.1 展示 Docling 如何把多格式文件转换为统一文档模型，但不能回答递归、父子和语义切片在同一语料上的差异。V3.11.2 引入 LangChain 与 LlamaIndex 的官方组件，建立可重复的框架对比实验，让学习重点落在组件职责、检索行为和取舍上。

## What Changes

- LangChain 路线使用 `RecursiveCharacterTextSplitter` 和 `ParentDocumentRetriever`，展示“小 child 召回、大 parent 返回”。
- LlamaIndex 层级路线使用 `HierarchicalNodeParser`、`VectorStoreIndex` 与 `AutoMergingRetriever`。
- LlamaIndex 语义路线使用 `SemanticSplitterNodeParser`，展示 embedding 驱动的主题边界。
- 三条路线复用 V3.11.1 Docling 转换出的 Markdown/metadata，并使用同一个现有 embedding client。
- 新增独立 `obsidian_rag/v3_11_2/` FastAPI JSON/Swagger、CLI 和 compare service；每次 compare 在内存中构建实验索引，不改写共享 Qdrant。
- 返回每个框架的 chunks/nodes、parent context、命中结果、构建耗时和统计信息，支持同问题横向对比。

## Capabilities

### New Capabilities

- `chunking-framework-comparison`: 对同一 Docling 文档执行 LangChain 父子检索、LlamaIndex 层级检索和语义切片，并返回统一可比较结果。

### Modified Capabilities

无。

## Impact

- 新增 LangChain、langchain-classic、langchain-text-splitters 与 llama-index-core 依赖。
- 新增 `obsidian_rag/v3_11_2/`、CLI、Swagger、测试、学习文档与 SVG。
- 不修改 V3.11.1 Docling 索引，也不改变 V0～V3.11 生产检索路径。
- V3.12 MCP Integration 继续作为下一主线版本。
