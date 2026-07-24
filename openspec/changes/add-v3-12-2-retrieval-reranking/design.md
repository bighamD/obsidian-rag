## Context

V3.12.1 的单库检索由 Dense/Keyword 召回、RRF 和 `expand_parent_results` 组成，多库检索还会执行第二层 cross-collection RRF。最终 `ContextBuilder` 仅按现有 score 排序并截断，没有模型理解 `query + candidate` 的阶段。Parent-Child 索引中真正被召回的是 child，扩展后返回给 LLM 的是 parent，因此重排既要利用 matched child 的精准语义，又要保留 parent 的完整上下文。

V3.12.2 是 V3.13 Permission Policy 前的 Retrieval Quality 插入版本。现有 Collection、keyword index、chunk schema、Prompt、Memory 和 Tool 权限语义必须保持不变；本地模型依赖较重且首次运行可能下载权重，不能让基础安装和无模型测试被强制绑定。

## Goals / Non-Goals

**Goals:**

- 明确区分 Recall、RRF、Reranker、Parent Expansion 和 ContextBuilder 的职责。
- 为单 Collection 与多 Collection 候选提供统一、可插拔、可测试的重排 contract。
- 用本地 CrossEncoder 演示真实 `query + chunk` 相关性打分，并保留 RRF 基线和完整可观测数据。
- Reranker 不可用时自动回退，回答链路继续工作且明确暴露 fallback。
- 用离线指标和固定案例验证收益与延迟，而不是只观察模型分数。

**Non-Goals:**

- 不重新切片、重新 Embedding 或迁移现有 Collection/keyword index。
- 不在本版本实现训练、微调、蒸馏或在线反馈学习。
- 不把 Cohere、Jina 等商业 API 作为首个必需实现，也不实现 GPU 服务编排和模型服务集群。
- 不修改 V3.12.1 契约，不把 Reranker 塞入 V3.13 Permission Policy。
- 不用 Reranker score 替代现有绝对相关性阈值，阈值校准作为后续课题。

## Decisions

### 1. 使用稳定 Adapter contract，而不是绑定框架 wrapper

新增公共 reranking package，核心 contract 接收 query 和有序候选，返回带原始 rank/score、rerank rank/score 和 metadata 的结果及运行摘要。V3.12.2 通过依赖注入使用该 contract。

LangChain 和 LlamaIndex 的 wrapper 适合快速接线，但会把学习重点隐藏在框架对象与 callback 中；本项目已经有稳定 RetrievalService、ContextBuilder 和 schemas，因此直接定义小型 contract 更容易观察数据流，也便于以后接入远端 API。

### 2. 首个真实实现选择 `sentence-transformers CrossEncoder`

`sentence-transformers` 提供通用的 Hugging Face sequence-classification 推理接口、batch、device 和常见 CrossEncoder 模型兼容能力。默认推荐模型为 `BAAI/bge-reranker-v2-m3`，原因是中英文/多语言知识库适配更好，且方向与生产 RAG 常见 BGE Reranker 一致。

同时提供 `none` 实现作为当前 RRF 基线。`sentence-transformers` 放入可选 `rerank` dependency extra，模型延迟加载；单元测试使用 deterministic fake，不下载权重。

备选方案：

- `FlagEmbedding`：更贴近 BGE 官方能力，适合 layerwise/LLM reranker 等高级模型，但首版 API 和依赖更专用、更重；后续需要 BGE 特有推理能力时再增加 provider。
- Cohere/Jina Rerank API：生产托管方便，但引入网络、密钥、成本和外部可用性，无法作为离线学习基线；后续按同一 contract 增加远端 Adapter。
- LLM listwise rerank：成本、延迟和稳定性较差，且混淆检索质量与生成模型能力，本版本不采用。

### 3. 扩大召回候选后重排，最终才截断 Context

目标链路为：

```text
Dense + Keyword
    -> RRF recall candidates
    -> Parent collapse / expansion
    -> Reranker(query, matched child text)
    -> rerank_top_k
    -> ContextBuilder / token budget
    -> Answer LLM
```

默认建议 `candidate_k=20`、`top_k=5`。Parent-Child 候选使用 `matched_child_text` 进行相关性打分，缺失时回退到当前 chunk text；重排后仍把 `returned_parent_text` 交给 ContextBuilder。这样避免用约 1000-token parent 稀释 child 的匹配信号，同时保留完整回答上下文。

多 Collection 必须先在受限 collection scope 内召回和融合足够候选，再统一执行一次 Reranker；不能在每个 Collection 内先截成最终 Top K，也不能直接比较不同 Collection 的原始 Dense/BM25 分数。

### 4. 原始排序信息不可覆盖

Reranker 结果单独记录 `retrieval_rank`、`retrieval_score`、`rerank_rank` 和 `rerank_score`。现有 `SearchResult.score` 的兼容语义不静默改写；V3.12.2 的 Context 排序使用明确的 rerank rank，Trace/API/Inspector 同时展示前后变化。

运行摘要记录 provider、model、device、candidate count、output count、latency、fallback 和安全错误摘要，便于比较质量与性能。

### 5. 失败采用 fail-open 回退 RRF

依赖缺失、模型下载/加载失败、推理异常或超过配置 timeout 时，系统 SHALL 保留原候选顺序并标记 fallback。空候选不加载模型。`RAG_RERANK_ENABLED=false` 或 provider=`none` 时明确返回 baseline 状态，而不是伪造 rerank score。

### 6. V3.12.2 保持独立教学入口

新增独立 FastAPI JSON/SSE、CLI、schemas、service 和调试配置。公共 contract 与实现放在无版本号共享模块中，V3.12.2 负责教学编排；V3.12.1 不改变，后续版本可显式选择复用。

配置建议：

```env
RAG_RERANK_ENABLED=true
RAG_RERANK_PROVIDER=sentence_transformers
RAG_RERANK_MODEL=BAAI/bge-reranker-v2-m3
RAG_RERANK_CANDIDATES=20
RAG_RERANK_TOP_K=5
RAG_RERANK_TIMEOUT_SECONDS=10
RAG_RERANK_DEVICE=auto
RAG_RERANK_BATCH_SIZE=8
```

### 7. 离线评估必须包含无模型基线

评估输入包含 query、相关 chunk/parent 标识和可选 collection。一次运行复用同一召回候选，分别计算 RRF baseline 与 Reranker 的 MRR、NDCG@K、Hit/Recall@K、最终 Context 命中和 latency，输出逐题排名变化。固定测试通过 fake reranker 构造“RRF Top 1 错、rerank 纠正”的案例。

## Risks / Trade-offs

- [BGE v2-m3 在 CPU/Mac 首次加载较慢且权重较大] → 可选依赖、延迟加载、device/batch 可配置；文档提供更轻量 CrossEncoder 替换示例。
- [线程 timeout 不能可靠中断底层 PyTorch 推理] → timeout 作为调用边界与回退信号，生产化阶段再采用独立模型服务实现硬超时和资源隔离。
- [Reranker score 不同模型间不可直接比较] → 不覆盖原 score，不默认复用 `RAG_MIN_SCORE`，评估按 rank 指标比较。
- [Parent 文本过长会稀释相关性] → 使用 matched child + heading context 打分，parent 仅作为最终 Context。
- [候选过少限制重排收益，过多增加延迟] → 独立配置 candidate_k/top_k，并在评估输出质量—延迟对照。
- [多 Collection 某一路失败] → 保留现有局部成功语义，对成功候选统一重排并记录 collection errors。

## Migration Plan

1. 增加公共 contract、`none`/CrossEncoder 实现、配置和 fake 单元测试，不接入既有版本。
2. 增加 V3.12.2 检索编排，在扩大召回、Parent collapse 后接入 Reranker。
3. 接入 Agent Core JSON/SSE 与 Trace，增加 API/CLI/多 Collection/fallback 测试。
4. 增加离线评估、文档、SVG、断点和 roadmap 说明。
5. 用户安装 `.[rerank]` 并显式打开配置后下载/加载真实模型；未安装或关闭时运行 RRF baseline。

回滚只需停止 V3.12.2 并继续运行 V3.12.1，或设置 `RAG_RERANK_ENABLED=false`；索引和 Memory 数据无需处理。

## Open Questions

- 真实模型验收时采用 `BAAI/bge-reranker-v2-m3` 还是先用更轻量模型，取决于本机下载时间和 CPU/MPS 实测；contract 和默认推荐不受影响。
- 将来生产部署是进程内 CrossEncoder 还是独立 Rerank 服务，需要在获得吞吐、P95 和并发数据后决定。
