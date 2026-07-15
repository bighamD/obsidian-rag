## ADDED Requirements

### Requirement: Common Docling source
系统 SHALL 将同一个 Docling 转换结果作为 LangChain 和 LlamaIndex 的输入，并为三条 strategy 使用相同 query、embedding provider 和 top_k。

#### Scenario: Compare one source
- **WHEN** 用户提交一个本地文件和 query
- **THEN** 三条 strategy 使用同一份 Docling Markdown 与 source metadata 构建实验索引

### Requirement: LangChain parent retrieval
系统 SHALL 使用 LangChain `RecursiveCharacterTextSplitter` 与 `ParentDocumentRetriever`，小 child 参与向量召回并返回较大的 parent documents。

#### Scenario: Retrieve LangChain parents
- **WHEN** LangChain child 向量命中 query
- **THEN** 响应同时展示 child similarity hits 和 ParentDocumentRetriever 返回的 parent context

### Requirement: LlamaIndex hierarchical retrieval
系统 SHALL 使用 LlamaIndex `HierarchicalNodeParser`、`VectorStoreIndex` 和 `AutoMergingRetriever` 构建层级节点并返回自动合并结果。

#### Scenario: Auto merge leaf nodes
- **WHEN** 多个相关 leaf nodes 属于同一个 parent
- **THEN** 响应展示 leaf/node 统计和 AutoMergingRetriever 最终返回的 context nodes

### Requirement: LlamaIndex semantic splitting
系统 SHALL 使用 `SemanticSplitterNodeParser` 和同一 embedding adapter 生成语义 chunks，并返回检索结果与边界统计。

#### Scenario: Build semantic chunks
- **WHEN** 文档包含多个自然语言主题段落
- **THEN** 系统返回语义 nodes、构建耗时和 query 检索结果

### Requirement: Unified observable comparison
系统 SHALL 提供独立 FastAPI JSON/Swagger 与 CLI，以统一 schema 返回 framework、strategy、配置、chunk/node 统计、preview 和 retrieval hits，且不写入共享 Qdrant。

#### Scenario: Compare all strategies
- **WHEN** 用户调用 compare API 或 CLI
- **THEN** 响应包含 LangChain parent、LlamaIndex hierarchical 和 LlamaIndex semantic 三项结果及总 trace

#### Scenario: Framework dependency missing
- **WHEN** 对应框架依赖未安装
- **THEN** 系统返回明确安装提示，不返回模糊 ImportError
