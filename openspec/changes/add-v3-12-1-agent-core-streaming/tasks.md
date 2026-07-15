## 1. 公共 Core 契约

- [x] 1.1 新增 `obsidian_rag/core/` schemas、Context、Memory、Compaction 和 Agent contract，确保 Core 不 import `v3_x`。
- [x] 1.2 新增公共 Chat Client complete/stream 能力和 AgentEvent/AnswerStreamMetrics contract。
- [x] 1.3 新增统一本地 Tool Registry contract，并通过 Adapter 接入 V3.12 MCP Tool/Result。

## 2. Agent 主线迁移

- [x] 2.1 将稳定 Agent Graph/Service 提升到 Core，保持 Planner、Retrieval、Evidence、Context、Memory 和 Answer 语义。
- [x] 2.2 将 V3.10、V3.10.2 和 V3.11 当前主线切换到 Core，移除对 V3.8.1 AgentService/schemas 的直接 import。
- [x] 2.3 保留 V3.8.1、V3.10.3 和 V3.12 教学入口兼容，并增加依赖方向静态测试。

## 3. 可见答案流

- [x] 3.1 在 Core Answer 节点复用 OpenAI-compatible streaming，发布带 message_id/sequence 的 `answer_delta` 并聚合最终答案。
- [x] 3.2 实现非流式回退、隐藏推理过滤以及 `llm_ttft_ms`/`llm_generation_ms` 观测。
- [x] 3.3 更新 V3.10.2/V3.11 Runtime SSE 映射，保持 `run_succeeded` 完整响应和 JSON 行为兼容。

## 4. Agent Console

- [x] 4.1 扩展前端 SSE 类型与 reducer，在同一个临时 assistant 消息中去重追加 `answer_delta`。
- [x] 4.2 在终态响应对账文本、sources、Run 和 Memory，并覆盖正常流、回退、重复 delta 与中断测试。

## 5. V3.12.1 学习闭环

- [x] 5.1 新增独立 `obsidian_rag/v3_12_1/` FastAPI JSON/SSE、schemas、service、dependencies 和 routes。
- [x] 5.2 增加 `agent-v3-12-1` CLI、Swagger payload、service/API/CLI 和 Core 单元测试。
- [x] 5.3 更新 roadmap、README、学习文档、文件职责、边界、正常/条件分支和 SVG 流程图。
- [x] 5.4 增加 VS Code 调试配置，核对真实断点行号并运行前后端、静态和 OpenSpec strict 验证。
