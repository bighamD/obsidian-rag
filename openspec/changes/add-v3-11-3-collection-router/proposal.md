## Why

当前已经存在 `food_safety`、`recipes`、`vueuse_core_kb` 等独立 collection，但统一入口只能依赖调用方准确填写 collection，前端也缺少该参数。随着知识库数量增加，需要一个可观察的 Registry 和 Collection Router，在未显式指定时选择有限范围，并在多库场景下安全融合检索结果。

## What Changes

- 为现有 Vue Agent Console 增加 collection 输入，并在 JSON/SSE 请求中透传 `collection`。
- 新增独立 `obsidian_rag/v3_11_3/` 学习版本，不把查询路由职责混入 V3.11.1 Docling ingest。
- 提供 YAML Knowledge Base Registry，记录知识库 ID、物理 collection、描述、triggers 和启用状态。
- collection 显式指定时跳过 LLM Router；未指定时由 LLM 选择零个、一个或最多两个知识库。
- 对选中的 collection 并行执行现有 dense/keyword/hybrid retrieval，并以跨库 RRF 生成统一结果。
- 返回结构化选择状态、置信度、候选库、各库命中数、融合结果和可观察 trace。
- 提供 FastAPI JSON、CLI、VS Code 调试配置、单元测试、学习文档和 SVG 主流程图。
- 这是 V3.12 MCP Integration 前的专项插入版本；完成后回到 V3.12 主线。

## Capabilities

### New Capabilities

- `collection-routing-retrieval`: 基于 Registry 和显式优先规则选择有限 collection，并执行可观察的单库或跨库 hybrid retrieval。

### Modified Capabilities

- 无；仓库尚未建立对应的基线 OpenSpec capability。

## Impact

- 前端：`frontend/v3_10_1_agent_console/` 的请求参数、类型和运行参数 UI。
- 后端：新增 `obsidian_rag/v3_11_3/`，复用 V1 `RetrievalService`、V3.11 LLM JSON Router 风格和现有 Qdrant/keyword indexes。
- 配置：新增 `knowledge_bases.yaml` 与可覆盖的 Registry 路径配置，不增加第三方依赖。
- 接口：新增 V3.11.3 collection list、route、search JSON API；不修改 V3.11.1 ingest API。
- 当前不接入完整 Agent、SSE、ACL、租户隔离、Qdrant sparse vector、reranker 或 alias 切换。
