## 1. 公共 Reranker 基础

- [x] 1.1 在 `RagConfig` 和 `.env.example` 增加 enabled/provider/model/candidates/top_k/timeout/device/batch size 配置及校验。
- [x] 1.2 增加无版本号 reranking schemas/contract，定义候选、排名前后数据、运行摘要和 provider 接口。
- [x] 1.3 实现 `none` baseline、deterministic fake 和 fail-open 编排器，覆盖 disabled、empty、异常与 timeout 分支。
- [x] 1.4 增加延迟加载的 `sentence-transformers CrossEncoder` Adapter，并把本地模型依赖放入可选 `rerank` extra。

## 2. V3.12.2 检索与 Agent 集成

- [x] 2.1 增加扩大候选的单 Collection 检索路径，保留 Dense/Keyword/RRF 信息并在 Parent collapse 后统一重排。
- [x] 2.2 增加多 Collection 候选融合与统一重排，确保最终截断发生在 Reranker 之后并保留局部失败信息。
- [x] 2.3 把 rerank Top K 接入公共 ContextBuilder/Agent Runtime，使用 matched child 打分、returned parent 构建 Prompt。
- [x] 2.4 在 Trace、sources 和进度事件中增加 provider/model、候选数量、耗时、fallback 及前后排名，保持 V3.12.1 契约不变。

## 3. V3.12.2 独立学习入口

- [x] 3.1 创建 `obsidian_rag/v3_12_2/` 的 schemas、service、dependencies、routes 和 FastAPI app，提供 Swagger JSON/SSE 与运行配置接口。
- [x] 3.2 增加 `agent-v3-12-2` CLI 的 ask/stream/rerank 对照入口和可直接运行的示例参数。
- [x] 3.3 更新 `.vscode/launch.json`，只增加 server 配置，并让当前 Agent Console 可连接 V3.12.2 服务。
- [x] 3.4 在兼容的 Console Inspector 中展示 retrieval rank/score、rerank rank/score、模型、耗时和 fallback，不复制整套前端。

## 4. 离线评估与测试

- [x] 4.1 增加复用同一召回候选的 baseline/rerank 评估服务，计算 Hit/Recall@K、MRR、NDCG@K、Context 命中和 latency。
- [x] 4.2 增加 RRF Top 1 被纠正、空候选、重复 parent、多 Collection、依赖缺失、异常和 timeout 的公共/service 单元测试。
- [x] 4.3 增加 V3.12.2 API、SSE、CLI 和配置测试，测试默认使用 fake/none provider 且不下载真实模型。
- [x] 4.4 检查真实模型 smoke test 条件；当前环境未安装可选 `sentence-transformers`，按可选边界不自动下载大型权重，运行方式已写入文档。

## 5. 学习资料与验证

- [x] 5.1 编写 V3.12.2 学习文档，说明版本边界、工具选型、RRF/Reranker/ContextBuilder 区别、Swagger payload、配置和 fallback。
- [x] 5.2 增加文件职责、正常与条件分支、真实执行顺序断点表，并按完成时代码核对函数名和行号。
- [x] 5.3 增加符合现有风格的 SVG 主流程图，展示单库、多库、RRF、Parent、Reranker、Context 和 LLM。
- [x] 5.4 谨慎合并更新 roadmap，说明 V3.12.2 是插入版本且完成后回到 V3.13 Permission Policy，不覆盖工作树现有修改。
- [x] 5.5 运行针对性单元测试、CLI/API 静态导入、前端检查和 `openspec validate add-v3-12-2-retrieval-reranking --strict`，修复失败并勾选任务。
