## ADDED Requirements

### Requirement: Agent Console 传递 collection
Agent Console SHALL 提供 collection 输入，并在 JSON/SSE Agent 请求中传递可选 `collection`；空白输入 MUST 转换为 null。

#### Scenario: 前端显式选择菜谱库
- **WHEN** 用户在运行参数中填写 `recipes` 并提交问题
- **THEN** 请求 payload 的 `collection` 为 `recipes`

#### Scenario: 前端留空
- **WHEN** 用户清空 collection 输入并提交问题
- **THEN** 请求 payload 的 `collection` 为 null，交由后端默认值或 Router 决定

### Requirement: Knowledge Base Registry
V3.11.3 SHALL 从 YAML Registry 加载知识库 ID、物理 collection、描述、triggers 和启用状态，并 MUST 拒绝重复 ID、重复 collection 或非法 collection 名称。

#### Scenario: 列出启用知识库
- **WHEN** Registry 包含 food_safety、recipes 和 vueuse_core_kb
- **THEN** `GET /collections` 和 CLI list 返回这三个可路由知识库的结构化元数据

#### Scenario: Registry 配置无效
- **WHEN** Registry 包含重复 collection 或非法名称
- **THEN** Registry 返回可读错误且不得把无效项作为 Router candidate

### Requirement: 显式 collection 优先
路由服务 MUST 在请求提供 collection 时跳过 LLM，并 MUST 只选择 Registry 中存在且启用的对应知识库。

#### Scenario: 显式选择 recipes
- **WHEN** 请求包含 `collection: recipes`
- **THEN** selection status 为 `explicit`、selected collections 仅包含 recipes，且 LLM Router 不被调用

#### Scenario: 显式选择未知 collection
- **WHEN** 请求包含合法格式但未登记的 collection
- **THEN** selection status 为 `invalid_selection`，检索结果为空并返回可观察原因

### Requirement: LLM Collection Router
请求未显式指定 collection 且 Router 启用时，系统 SHALL 使用 Registry metadata 让 LLM 选择零个、一个或有限多个知识库。选择数量 MUST 不超过请求 `max_collections`，且所有选择 MUST 来自启用 candidates。

#### Scenario: 选择一个知识库
- **WHEN** 问题是“useMouse 怎么使用”且 Router 返回 vueuse_core
- **THEN** selection status 为 `selected`，只检索 vueuse_core_kb

#### Scenario: 选择两个知识库
- **WHEN** 问题同时涉及鸡肉做法和食品安全，Router 返回 recipes 与 food_safety
- **THEN** selection status 为 `multi_selected`，系统只查询这两个 collection

#### Scenario: 没有适用知识库
- **WHEN** LLM 返回空 collection 列表
- **THEN** selection status 为 `no_collection`，不执行检索

#### Scenario: Router 返回未知或过多选择
- **WHEN** LLM 返回 Registry 外 collection 或超过 max_collections
- **THEN** selection status 为 `invalid_selection`，不得执行越界检索

#### Scenario: Router 输出不可解析
- **WHEN** LLM 未返回合法 JSON
- **THEN** selection status 为 `router_error`，响应保留错误摘要且不执行检索

### Requirement: 多 collection Hybrid Retrieval
系统 SHALL 对选中的每个 collection 调用现有 RetrievalService，并在多库时并行执行。每个命中 MUST 标明实际 collection，一个 collection 失败时其他成功 collection 的结果 SHALL 保留。

#### Scenario: 单库检索
- **WHEN** selection 只包含 food_safety
- **THEN** 系统只加载 food_safety 的 Qdrant collection 和 keyword index

#### Scenario: 双库并行检索
- **WHEN** selection 包含 recipes 与 food_safety
- **THEN** 两个 collection 分别执行请求的 dense、keyword 或 hybrid mode，响应返回各库命中数

#### Scenario: 一个 collection 检索失败
- **WHEN** 双库检索中 recipes 成功而 food_safety 失败
- **THEN** 响应保留 recipes 结果，并在 collection errors 中记录 food_safety 错误

### Requirement: 跨 collection RRF
多库检索结果 SHALL 使用第二层 RRF 按 collection 内排名融合。去重 key MUST 包含 collection，响应 MUST 提供 collection rank 和 cross-collection score。

#### Scenario: 两库融合
- **WHEN** recipes 与 food_safety 各返回候选结果
- **THEN** 系统按两库内部排名计算跨库 RRF，并返回全局 top_k

#### Scenario: 相同 chunk_id 不跨库误合并
- **WHEN** 两个 collection 都存在 `chunk_id: KB-001`
- **THEN** 两条结果因 collection 不同而保持独立

### Requirement: V3.11.3 学习闭环与边界
V3.11.3 SHALL 提供独立目录、FastAPI JSON、CLI、Pydantic 字段说明、单元测试、学习文档、SVG 和可执行断点配置。版本文档 MUST 说明它是 V3.12 前的专项插入，并且当前不接完整 Agent、SSE、ACL、Qdrant sparse 或 reranker。

#### Scenario: Swagger 调试
- **WHEN** 用户启动 V3.11.3 app
- **THEN** Swagger 可测试 list、route 和 search JSON 接口并解释关键字段

#### Scenario: CLI 调试
- **WHEN** 用户运行 `collections-v3-11-3 route` 或 `search`
- **THEN** CLI 输出与 API 相同的结构化 JSON 结果
