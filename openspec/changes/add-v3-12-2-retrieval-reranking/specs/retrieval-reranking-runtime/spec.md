## ADDED Requirements

### Requirement: 可插拔 Reranker contract
系统 SHALL 提供无版本号的 Reranker contract，接收 query 和有序候选，并返回包含原始排名、原始分数、重排排名、重排分数及运行摘要的结果。V3.12.2 SHALL 通过依赖注入使用该 contract，而不是依赖 LangChain 或 LlamaIndex 的内部结果类型。

#### Scenario: Fake Reranker 改变候选顺序
- **WHEN** 测试注入 deterministic fake reranker 并传入多个候选
- **THEN** 系统按照 rerank score 返回新顺序，同时保留每个候选的原始 rank 和 score

### Requirement: RRF baseline 与本地 CrossEncoder
系统 SHALL 提供不改变候选顺序的 `none` baseline，并 SHALL 提供基于 `sentence-transformers CrossEncoder` 的本地实现。模型名称、device 和 batch size MUST 可配置，真实模型 MUST 延迟加载。

#### Scenario: Reranker 被关闭
- **WHEN** `RAG_RERANK_ENABLED=false` 或 provider 为 `none`
- **THEN** 系统保持 RRF 候选顺序并在运行摘要中标记 baseline，且不加载模型

#### Scenario: 本地模型执行重排
- **WHEN** Reranker 已启用、可选依赖可用且候选非空
- **THEN** 系统以 query-candidate pair 批量调用配置的 CrossEncoder，并按模型分数生成 rerank rank

### Requirement: Parent-Child 重排语义
系统 SHALL 在足量召回和 RRF 后对唯一 Parent 候选执行重排。Parent-Child 候选 MUST 优先使用 `matched_child_text` 与标题上下文进行模型打分，最终 Context MUST 使用 `returned_parent_text`；缺少这些字段时 SHALL 回退到当前 chunk text。

#### Scenario: Child 命中返回 Parent
- **WHEN** 候选 metadata 同时包含 `matched_child_text` 和 `returned_parent_text`
- **THEN** Reranker 使用 matched child 计算相关性，ContextBuilder 接收对应 parent 内容

#### Scenario: 非 Parent-Child 旧数据
- **WHEN** 候选不包含 Parent-Child metadata
- **THEN** 系统使用候选自身文本完成重排且不报错

### Requirement: 先扩大候选再最终截断
V3.12.2 SHALL 区分 recall candidate count 与最终 rerank Top K。单 Collection 和多 Collection 都 MUST 在获得配置数量的候选后统一重排，ContextBuilder MUST 只接收最终 Top K。

#### Scenario: 单 Collection 重排
- **WHEN** 单 Collection 返回多于最终 Top K 的候选
- **THEN** 系统重排全部候选并只把 rerank Top K 交给 ContextBuilder

#### Scenario: 多 Collection 统一重排
- **WHEN** Collection Router 选择多个 Collection 且各自返回候选
- **THEN** 系统完成受限范围内的跨库融合后统一重排，不直接比较不同 Collection 的原始 Dense 或 BM25 分数

### Requirement: Fail-open 回退
Reranker 依赖缺失、模型加载失败、推理异常或超过配置 timeout 时，系统 SHALL 回退到输入候选顺序并继续回答。响应和 Trace MUST 标记 fallback、阶段、耗时及安全错误摘要。

#### Scenario: 模型推理失败
- **WHEN** CrossEncoder 在候选打分时抛出异常
- **THEN** 系统按 RRF 顺序继续构建 Context，并在运行摘要中返回 `fallback=true`

#### Scenario: 空候选
- **WHEN** 检索没有返回候选
- **THEN** 系统返回空重排结果且不加载或调用模型

### Requirement: 重排可观测性
V3.12.2 API、Trace 和调试响应 SHALL 暴露 provider、model、候选数量、输出数量、耗时、fallback，以及每个候选的 retrieval/rerank rank 和 score。系统 MUST 不静默覆盖现有 retrieval score 语义。

#### Scenario: 查看排序变化
- **WHEN** Reranker 调整了候选顺序
- **THEN** 调试输出能够同时显示调整前后的排名和分数，并能定位候选 source、collection、chunk_id 或 parent_id

### Requirement: V3.12.2 独立学习闭环
V3.12.2 SHALL 提供独立目录、FastAPI JSON/SSE、CLI、带中文职责及 `Field(description=...)` 的 Pydantic schemas、service/API/CLI 测试、学习文档、SVG、文件职责说明和按当前代码行号核对的断点配置。文档 MUST 说明正常链路、disabled、empty、timeout、fallback 和 multi-collection 分支。

#### Scenario: Swagger 学习重排
- **WHEN** 用户启动 V3.12.2 FastAPI app 并提交文档中的示例 payload
- **THEN** 用户能够观察完整回答以及候选重排摘要

#### Scenario: CLI 对照运行
- **WHEN** 用户分别以 baseline 和 CrossEncoder 配置运行 V3.12.2 CLI
- **THEN** CLI 输出排序变化、来源、耗时和 fallback 状态

### Requirement: 版本与数据兼容
V3.12.2 SHALL 复用现有 Collection、keyword index、chunk schema、Agent Core 和 Memory 数据，且 MUST 不改变 V3.12.1 对外契约。关闭 V3.12.2 或 Reranker 后 SHALL 可直接回到原链路。

#### Scenario: 使用已有索引
- **WHEN** 用户已用 adaptive parent-child 策略建立 Collection
- **THEN** V3.12.2 可以直接检索和重排，不要求重新 ingest

