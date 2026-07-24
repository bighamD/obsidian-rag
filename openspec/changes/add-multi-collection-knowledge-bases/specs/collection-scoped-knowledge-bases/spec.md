## ADDED Requirements

### Requirement: 请求级 collection 选择
系统 SHALL 允许 ingest、search、ask 和 Agent ask 请求指定可选 `collection`。collection 未提供时，系统 SHALL 使用 `RAG_COLLECTION` 配置值；collection 提供时，系统 MUST 仅在该请求范围内使用它，且不得修改共享全局 config。collection 名称 MUST 匹配 `[a-z0-9][a-z0-9_-]{0,62}`。

#### Scenario: 使用默认 collection
- **WHEN** 调用方未提供 collection 且 `RAG_COLLECTION=obsidian_notes`
- **THEN** 请求在 `obsidian_notes` 中执行并在响应中回显该名称

#### Scenario: 使用显式 collection
- **WHEN** 调用方传入 `collection: food_safety`
- **THEN** 本次请求只使用 `food_safety` 的存储和检索资源

#### Scenario: 拒绝非法 collection
- **WHEN** 调用方传入包含空格或大写字母的 collection 名称
- **THEN** 系统拒绝请求并说明合法命名格式

### Requirement: Dense 与 keyword collection 隔离
系统 SHALL 将每个 collection 的 KeywordIndex 写入独立的 collection-derived 文件，并在 keyword / hybrid retrieval 时读取同一个文件。系统 MUST 不得让一个 collection 的 keyword 结果参与另一个 collection 的 hybrid RRF。

#### Scenario: 两个 collection 先后 ingest
- **WHEN** `food_safety` 和 `recipes` 分别执行 ingest
- **THEN** 两者拥有独立 Qdrant collection 和独立 keyword index 文件

#### Scenario: 在指定 collection 执行 hybrid search
- **WHEN** 调用方以 `collection: recipes` 执行 hybrid search
- **THEN** dense 和 keyword 两条结果都只来源于 `recipes`

### Requirement: collection-scoped ingest 重建
系统 SHALL 让 `recreate=true` 只重建请求指定的 Qdrant collection 并覆盖对应 keyword index。系统 MUST 不得删除或重建其他 collection。

#### Scenario: 重建食品安全 collection
- **WHEN** `food_safety` 使用 `recreate=true` ingest
- **THEN** `food_safety` 被重建，`recipes` 中已有向量和 keyword index 保持不变

#### Scenario: 增量写入当前 collection
- **WHEN** 同一个 collection 先以 `recreate=true` ingest 第一批文档，再以 `recreate=false` ingest 第二批文档
- **THEN** dense 与 keyword 检索都能访问两批文档，且不影响其他 collection

### Requirement: 公共 API、CLI 和 Agent 贯通
V0 API / CLI、V3.11.1 Docling API / CLI 和 V3.8.1/3.11 Agent SHALL 传播一次请求选定的 collection。所有写入或检索响应 SHALL 回显实际使用的 collection；只读 convert/chunks preview 不要求 collection。

#### Scenario: Docling CLI 指定 collection
- **WHEN** 用户执行 `documents-v3-11-1 ingest ... --collection food_safety --recreate`
- **THEN** Docling chunks 只写入 `food_safety`，JSON response 回显 `food_safety`

#### Scenario: Agent 的重试检索保持 collection
- **WHEN** Agent ask 指定 `collection: recipes` 且 Evidence Checker 触发 retry search
- **THEN** 初始 search 与 retry search 都只查询 `recipes`
