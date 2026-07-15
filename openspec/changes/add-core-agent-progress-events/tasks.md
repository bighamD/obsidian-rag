## 1. Core 与 Runtime

- [x] 1.1 新增 AgentProgressEvent schema、稳定 phase 映射和 running/completed progress 发布。
- [x] 1.2 在 retrieval progress 中提供 collection 与聚合 result_count，并保持 trace/answer_delta 兼容。
- [x] 1.3 验证 V3.10.2/V3.11 Runtime 通过 EventBus 转发 progress。

## 2. Agent Console

- [x] 2.1 增加 progress 类型、reducer 和单行当前状态展示。
- [x] 2.2 完成后展示 collection、检索数、总耗时、TTFT 和 Memory 状态。
- [x] 2.3 增加 V3.12.1 UI server，并确保 launch.json 不包含 CLI 配置。

## 3. 验证与文档

- [x] 3.1 补 Core/Runtime progress 和前端 reducer 单元测试。
- [x] 3.2 更新 V3.12.1 学习文档并运行前后端、静态和 OpenSpec strict 验证。
