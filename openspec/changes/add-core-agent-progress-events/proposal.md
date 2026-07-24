## Why

V3.12.1 已能流式输出最终答案，但首 token 前前端只显示“正在生成回答”，没有呈现 Memory、Planner、Retrieval、Evidence 等真实阶段。后续 Permission、Sandbox 和 HITL 也需要同一套稳定进度契约，因此应由公共 Core 产生领域无关的进度事实，而不是让前端绑定 LangGraph 节点名。

## What Changes

- 在公共 Core 增加稳定 `progress` 事件，包含 `phase`、`status`、`collection`、`result_count` 等事实字段。
- Core 把现有 Agent 节点映射为 memory、planning、retrieval、evidence、context、answer、memory_write 阶段。
- Runtime 继续通过统一 SSE EventBus 转发 progress，不把 UI 中文文案写入 Core。
- Agent Console 使用 progress reducer 显示单行当前状态，并在 `answer_delta` 到达后继续同气泡增量回答。
- 完成后显示 collection、检索结果数、总耗时、TTFT 和 Memory 写入状态。
- `launch.json` 增加指向 V3.12.1 `8020` 的 Vite UI server，并继续只保留 server 配置。

## Capabilities

### New Capabilities

- `agent-progress-events`: 公共 Agent 阶段进度契约、SSE 转发和前端稳定状态展示。

### Modified Capabilities

- 无。

## Impact

- 后端：`obsidian_rag/core/schemas.py`、`core/agent/service.py`、V3.10.2/V3.11 Runtime。
- 前端：Agent stream types、composable reducer、ChatTranscript 和样式。
- 调试：`.vscode/launch.json` 新增 V3.12.1 UI server。
- 兼容：`answer_delta`、JSON response、终态 SSE 和 Agent 决策语义保持不变。
