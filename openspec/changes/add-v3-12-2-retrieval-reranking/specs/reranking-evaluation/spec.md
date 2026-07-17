## ADDED Requirements

### Requirement: Baseline 与 Reranker 使用同一候选集
离线评估 SHALL 对同一 query 复用同一批召回候选，分别计算 RRF baseline 和 Reranker 结果，避免召回波动污染对照结论。

#### Scenario: 执行对照评估
- **WHEN** 评估集包含 query 和相关 chunk/parent 标识
- **THEN** 一次评估输出同一候选集上的 baseline 与 reranked 排名结果

### Requirement: 排序质量和延迟指标
评估 SHALL 至少计算 Hit/Recall@K、MRR、NDCG@K、最终 Context 命中数量和 rerank latency，并 SHALL 输出逐题排名变化及汇总指标。

#### Scenario: Reranker 纠正错误 Top 1
- **WHEN** 相关候选在 RRF 中不是第一名而被 Reranker 提升到第一名
- **THEN** 逐题结果展示前后 rank，汇总结果反映 MRR/NDCG 改善及新增延迟

### Requirement: 固定回归案例
测试 SHALL 覆盖 RRF 排名错误被纠正、候选为空、相同 parent 去重、多 Collection 候选和 Reranker fallback，且 MUST 使用 fake reranker，不能依赖网络下载真实模型。

#### Scenario: 离线无网络测试
- **WHEN** 开发者在没有模型缓存和外网的环境运行单元测试
- **THEN** reranking service、API 和 CLI 测试仍能稳定完成

### Requirement: 评估结果不夸大收益
评估输出 SHALL 同时报告 baseline、Reranker、失败回退次数和延迟，不得只展示改善样本。学习文档 MUST 说明候选召回失败无法由 Reranker 修复。

#### Scenario: 相关文档未进入候选集
- **WHEN** 相关文档不在 recall candidates 中
- **THEN** 评估将该题记录为召回失败，且不宣称 Reranker 能够纠正

