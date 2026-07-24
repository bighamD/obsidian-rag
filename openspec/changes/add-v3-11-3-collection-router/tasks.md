## 1. Agent Console collection 参数

- [x] 1.1 为 AgentOptions、AgentAskPayload 和 AgentResponse 增加 collection 类型。
- [x] 1.2 在运行参数 UI 中增加 collection 输入并覆盖 payload 空值与显式值测试。

## 2. Registry 与 Router

- [x] 2.1 新增 `knowledge_bases.yaml` 和 KnowledgeBaseRegistry，覆盖合法、重复、禁用和错误配置。
- [x] 2.2 实现显式优先、disabled、单库、多库、no_collection、invalid_selection 和 router_error 分支。

## 3. 多库检索

- [x] 3.1 实现 request-scoped 多 collection retrieval，复用现有 dense/keyword/hybrid 并记录每库结果或错误。
- [x] 3.2 实现 collection-aware 跨库 RRF，保留同 chunk_id 的跨库独立结果。

## 4. V3.11.3 接口面

- [x] 4.1 建立独立 `obsidian_rag/v3_11_3/` schemas、service、dependencies、FastAPI list/route/search JSON 路由。
- [x] 4.2 增加 `collections-v3-11-3 list|route|search` CLI，并覆盖显式与自动路由调试案例。

## 5. 学习闭环

- [x] 5.1 补齐 service、API、CLI 单元测试和 Swagger payload 示例。
- [x] 5.2 更新 roadmap，新增 V3.11.3 学习文档、文件职责、边界、正常/异常分支和 SVG 流程图。
- [x] 5.3 增加 VS Code 调试配置，核对真实断点行号并运行前后端、静态和 OpenSpec strict 验证。
