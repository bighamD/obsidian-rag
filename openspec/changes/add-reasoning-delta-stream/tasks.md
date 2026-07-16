## 1. 配置与 LLM Contract

- [x] 1.1 增加 reasoning stream 环境配置、RagConfig 字段和 V3.12.1 Chat Client 注入。
- [x] 1.2 增加 ChatStreamDelta，并将 CPA reasoning_content/content 映射为类型化流。

## 2. Core 与 Runtime

- [x] 2.1 Core 发布独立 reasoning_delta，并增加 reasoning TTFT/字符数指标且保持最终 answer 隔离。
- [x] 2.2 V3.10.2/V3.11 Runtime 实时转发 reasoning_delta，不写入逐 chunk Run 历史。

## 3. Agent Console

- [x] 3.1 增加 reasoning 类型、reducer、独立 sequence 去重和响应式草稿字段。
- [x] 3.2 ChatTranscript 增加“思考过程（学习调试）”独立展示，不影响正文和终态摘要。

## 4. 验证与文档

- [x] 4.1 增加 Client/Core/Runtime 和前端 reasoning 单元测试。
- [x] 4.2 更新 V3.12.1 配置接口、学习文档并运行前后端、静态与 OpenSpec strict 验证。
