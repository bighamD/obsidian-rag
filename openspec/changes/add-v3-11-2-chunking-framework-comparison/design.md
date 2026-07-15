## Context

V3.11.1 已把原始多格式文件转换为 DoclingDocument/Markdown，并用 HybridChunker 写入共享索引。V3.11.2 是独立学习实验：相同 Docling Markdown、相同 embedding client 和相同 query，分别进入 LangChain 与 LlamaIndex，观察 chunks、父子关系和检索上下文差异。实验结果不应污染共享 Qdrant。

## Goals / Non-Goals

**Goals:**

- 实际调用 LangChain `RecursiveCharacterTextSplitter` 与 `ParentDocumentRetriever`。
- 实际调用 LlamaIndex `HierarchicalNodeParser`、`AutoMergingRetriever` 与 `SemanticSplitterNodeParser`。
- 用适配器复用仓库现有 OpenAI/Ollama/hash embedding client。
- 返回统一的 framework result schema，比较节点数、长度、耗时、命中 child 与最终 parent context。
- 提供 JSON API、Swagger、CLI、测试、断点文档和 SVG。

**Non-Goals:**

- 不把任一实验框架设为共享 V0 默认检索器。
- 不持久化 LangChain docstore 或 LlamaIndex storage context。
- 不调用 LLM 生成答案，不新增 SSE。
- 不宣称一次小样本 compare 等同于完整生产评估。

## Decisions

### 1. 每次 compare 建立内存实验索引

请求包含文件路径、query、parent/child 大小与 top_k。服务先通过 V3.11.1 Docling adapter 导出 Markdown，然后分别构建三条内存路线。这样 CLI 单次运行即可完整观察，不需要管理第二、第三套持久化索引。

### 2. LangChain 使用官方 ParentDocumentRetriever

使用两个 `RecursiveCharacterTextSplitter`：parent splitter 生成较大文档，child splitter 生成小文档。`ParentDocumentRetriever` 配合 `InMemoryVectorStore`、`InMemoryStore` 和现有 embedding adapter；结果返回 parent documents，并额外执行 child similarity search 供调试。

### 3. LlamaIndex 层级路线使用 AutoMergingRetriever

`HierarchicalNodeParser(chunk_sizes=[parent, child])` 生成全部 nodes；leaf nodes 建立 `VectorStoreIndex`，全部 nodes 写入 `StorageContext.docstore`，`AutoMergingRetriever` 根据命中叶节点自动合并父节点。

### 4. LlamaIndex 语义路线单独展示

`SemanticSplitterNodeParser` 使用同一 embedding adapter，根据相邻句子 embedding 差异生成 nodes，再以 `VectorStoreIndex` 检索。该路线没有结构 parent 合并，结果用于观察主题边界、chunk 数和召回差异。

### 5. 统一输出，不隐藏框架原语

每条 strategy 返回：framework、strategy、build_ms、chunk_count、平均/最大字符数、chunks preview、retrieval hits。hit 明确区分 matched child/node 与 returned context；同时保留框架 node/document ID 和 metadata。

## Risks / Trade-offs

- [每次请求重新 embedding，耗时和成本高] → 这是学习 API，限制单文件和 chunk 数；文档明确不要作为生产在线接口。
- [框架版本 API 变化] → 依赖限定 major version，导入集中在 adapter 模块并提供清晰错误。
- [不同框架 score 不可直接比较] → 只在同框架内解释排序；跨框架重点比较命中来源与上下文，不比较绝对分值。
- [SemanticSplitter 依赖 embedding 稳定性] → 返回配置和统计，并要求用 V2 真实问题集复测。

## Migration Plan

V3.11.2 不修改共享数据，无迁移。删除该版本目录和 CLI/launch 配置即可回滚。

## Open Questions

- 后续是否把最佳 strategy 接入共享 Qdrant，由 V2 evaluation 结果决定。
